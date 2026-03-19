# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from werkzeug import urls

from odoo import _, api, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_skipcash_qa import const
from odoo.addons.payment_skipcash_qa.controllers.main import SkipcashController

from decimal import Decimal
from skipcash.schema import PaymentInfo
from skipcash.exceptions import PaymentValidationError, PaymentInfoError
from skipcash.exceptions import PaymentRetrievalError, PaymentResponseError
from skipcash.api_resources import Payment

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _validate_amount(self, amount_data):
        """ Override of payment to bypass amount validation for Skipcash.
        SkipCash does not send the amount in the browser return payload.
        The transaction is securely verified via S2S API in _apply_updates.
        """
        if self.provider_code == 'skipcash':
            return
        return super()._validate_amount(amount_data)

    def _get_specific_processing_values(self, processing_values):
        res = super()._get_specific_processing_values(processing_values)
        if self._skipcash_is_authorization_pending():
            res['redirect_form_html'] = self.env['ir.qweb']._render(
                self.provider_id.redirect_form_view_id.id,
                {'api_url': self.provider_reference},
            )
        return res

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'skipcash':
            return res

        first_name, last_name = payment_utils.split_partner_name(self.partner_name)
        skipcash = self.provider_id.skipcash_get()
        payment_info = PaymentInfo(
            key_id=skipcash.key_id,
            amount=Decimal(str(self.amount)),
            first_name=first_name,
            last_name=last_name,
            phone=self.partner_phone,
            email=self.partner_email,
            street=(self.partner_address or '')[:50],
            city=(self.partner_city or '')[:50],
            transaction_id=self.reference,
        )

        try:
            payment = Payment(skipcash)
            response = payment.create_payment(payment_info)
            return {'api_url': response.pay_url}
        except PaymentInfoError as e:
            raise ValidationError("SkipCash Error: " + str(e))
        except PaymentValidationError as e:
            raise ValidationError("Validation Error: " + str(e))
        except PaymentResponseError as e:
            raise ValidationError("Response Error: " + str(e))

    def _send_payment_request(self):
        super()._send_payment_request()
        if self.provider_code != 'skipcash':
            return

        if not self.token_id:
            raise UserError("skipcash: " + _("The transaction is not linked to a token."))

        first_name, last_name = payment_utils.split_partner_name(self.partner_name)
        base_url = self.provider_id.get_base_url()
        data = {
            'token': self.token_id.provider_ref,
            'email': self.token_id.skipcash_customer_email,
            'amount': self.amount,
            'currency': self.currency_id.name,
            'country': self.company_id.country_id.code,
            'tx_ref': self.reference,
            'first_name': first_name,
            'last_name': last_name,
            'ip': payment_utils.get_customer_ip_address(),
            'redirect_url': urls.url_join(base_url, SkipcashController._auth_return_url),
        }

        response_content = self.provider_id._skipcash_make_request(
            'tokenized-charges', payload=data
        )
        self._process('skipcash', response_content['data'])

    @api.model
    def _extract_reference(self, provider_code, payment_data):
        res = super()._extract_reference(provider_code, payment_data)
        if provider_code != 'skipcash':
            return res
        return (
                payment_data.get('transId')
                or payment_data.get('reference')
                or payment_data.get('TransactionId')
        )

    def _get_skipcash_error_message(self, reason_code):
        codes = {
            '100': "Successful Transaction",
            '101': "Request is missing one or more required fields",
            '102': "One or more fields contain invalid data",
            '150': "General System Failure",
            '151': "The transaction timed out",
            '152': "The transaction timed out",
            '200': "The authorization request was approved by the issuing bank",
            '201': "The issuing bank has questions about the request",
            '202': "Expired card",
            '203': "General decline of the card",
            '204': "Insufficient funds in the account",
            '205': "Stolen or lost card",
            '208': "Inactive card / Card not authorized",
            '210': "The card has reached the credit limit",
            '211': "Invalid CVN (Security Code)",
            '221': "The customer is blacklisted",
            '231': "Invalid account number",
            '232': "The card type is not accepted by the payment processor",
            '240': "The card type sent is invalid or does not correlate with the payment card number",
            '475': "The cardholder is enrolled for Payer Authentication",
            '476': "Payer Authentication Failed (OTP/3D Secure Missing)",
            '481': "Transaction declined by Fraud Management",
        }
        return codes.get(str(reason_code), f"Unknown Decline (Code: {reason_code})")

    def _apply_updates(self, payment_data):
        super()._apply_updates(payment_data)
        if self.provider_code != 'skipcash':
            return

        skipcash = self.provider_id.skipcash_get()
        payment = Payment(skipcash)
        payment_id = payment_data.get('id') or payment_data.get('PaymentId')

        try:
            if not payment_id:
                raise ValidationError("SkipCash: No Payment ID found in notification data.")

            verified_data = payment.get_payment(payment_id)

        except (PaymentRetrievalError, ValidationError) as e:
            self._set_error("SkipCash verification failed. Manual check required.")
            return

        self.provider_reference = verified_data.id

        payment_method_type = getattr(verified_data, 'card_type', None)
        if payment_method_type:
            payment_method = self.env['payment.method']._get_from_code(
                payment_method_type.lower(), mapping=const.PAYMENT_METHODS_MAPPING
            )
            self.payment_method_id = payment_method or self.payment_method_id

        payment_status = getattr(verified_data, 'status', '')
        if not payment_status:
            status_id = getattr(verified_data, 'StatusId', None) or getattr(verified_data, 'status_id', None)
            if str(status_id) == '2':
                payment_status = 'paid'
            elif str(status_id) == '1':
                payment_status = 'pending'

        payment_status = payment_status.lower() if payment_status else ''

        if payment_status in const.PAYMENT_STATUS_MAPPING['pending']:
            self._set_pending()
        elif payment_status in const.PAYMENT_STATUS_MAPPING['done'] or payment_status == 'paid':
            self._set_done()
        elif payment_status in const.PAYMENT_STATUS_MAPPING['cancel']:
            self._set_canceled()
        elif payment_status in const.PAYMENT_STATUS_MAPPING['error']:
            reason_code = getattr(verified_data, 'ReasonCode', None) or payment_data.get('ReasonCode')
            error_msg = self._get_skipcash_error_message(reason_code)
            self._set_error(_("Payment Failed: %s", error_msg))
        else:
            self._set_error("skipcash: " + _("Unknown payment status: %s", payment_status))

    def _extract_token_values(self, payment_data):
        res = super()._extract_token_values(payment_data)
        if self.provider_code != 'skipcash':
            return res

        full_card = payment_data.get('CardNubmer') or payment_data.get('CardNumber')
        last_4 = full_card[-4:] if full_card else 'XXXX'
        provider_ref = payment_data.get('TokenId')
        email = payment_data.get('Email') or self.partner_email

        return {
            'payment_details': last_4,
            'provider_ref': provider_ref,
            'skipcash_customer_email': email,
        }

    def _skipcash_is_authorization_pending(self):
        return self.filtered_domain([
            ('provider_code', '=', 'skipcash'),
            ('operation', '=', 'online_token'),
            ('state', '=', 'pending'),
            ('provider_reference', 'ilike', 'https'),
        ])