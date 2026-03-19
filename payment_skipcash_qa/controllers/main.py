# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hmac
import json
import logging
import hashlib
import base64

from werkzeug.exceptions import Forbidden
from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class SkipcashController(http.Controller):
    _return_url = '/payment/skipcash/return'
    _auth_return_url = '/payment/skipcash/auth_return'
    _webhook_url = '/payment/skipcash/webhook'

    @http.route(_return_url, type='http', methods=['GET'], auth='public')
    def skipcash_return_from_checkout(self, **data):
        """ Process the notification data sent by skipcash after redirection from checkout. """
        payment_data = dict(data)

        # Standardize the reference key for Odoo 19
        if 'transId' in payment_data and 'reference' not in payment_data:
            payment_data['reference'] = payment_data['transId']

        if (payment_data.get('status') or '').lower() == 'cancelled':
            try:
                tx_sudo = request.env['payment.transaction'].sudo()._search_by_reference('skipcash', payment_data)
                tx_sudo._set_canceled()
            except Exception as e:
                _logger.error("SkipCash: Failed to cancel transaction: %s", e)
        else:
            # Pass data to core; amount validation is safely bypassed in models
            request.env['payment.transaction'].sudo()._process('skipcash', payment_data)

        return request.redirect('/payment/status')

    @http.route(_webhook_url, type='http', methods=['POST'], auth='public', csrf=False)
    def skipcash_webhook(self):
        """ Process the notification data sent by skipcash to the webhook. """
        data = request.get_json_data()
        detailed_data = data.get('data', data) if isinstance(data, dict) else data
        
        if isinstance(data, dict) and data.get('event') and data.get('event') != 'charge.completed':
            return request.make_json_response('')

        detailed_data = dict(detailed_data)

        if 'TransactionId' in detailed_data and 'transId' not in detailed_data:
            detailed_data['transId'] = detailed_data['TransactionId']
            
        if 'transId' in detailed_data and 'reference' not in detailed_data:
            detailed_data['reference'] = detailed_data['transId']

        try:
            if not detailed_data.get('reference'):
                return request.make_json_response('')

            tx_sudo = request.env['payment.transaction'].sudo()._search_by_reference('skipcash', detailed_data)

            signature = request.httprequest.headers.get('Authorization')
            self._verify_notification_signature(signature, tx_sudo, detailed_data)

            tx_sudo._process('skipcash', detailed_data)

        except ValidationError:
            _logger.exception("Unable to handle the notification data; skipping to acknowledge")
        except Exception as e:
            _logger.error("Unexpected error in SkipCash webhook: %s", e)

        return request.make_json_response('')

    @http.route(_auth_return_url, type='http', methods=['GET'], auth='public')
    def skipcash_return_from_authorization(self, response):
        """ Process the response sent by skipcash after authorization. """
        data = json.loads(response)
        return self.skipcash_return_from_checkout(**data)

    @staticmethod
    def _verify_notification_signature(received_signature, tx_sudo, data):
        """ Check that the received signature matches the expected one. """
        if not received_signature:
            raise Forbidden()

        secret = tx_sudo.provider_id.skipcash_webhook_key
        if not secret:
            raise Forbidden()

        def get_val(key):
            val = data.get(key)
            return str(val) if val is not None else ''

        fields = [
            f"PaymentId={get_val('PaymentId')}",
            f"Amount={get_val('Amount')}",
            f"StatusId={get_val('StatusId')}",
        ]
        if data.get('TransactionId'):
            fields.append(f"TransactionId={get_val('TransactionId')}")
        if data.get('Custom1'):
            fields.append(f"Custom1={get_val('Custom1')}")
        fields.append(f"VisaId={get_val('VisaId')}")

        signing_string = ",".join(fields)

        try:
            expected_signature_bytes = hmac.new(
                secret.encode('utf-8'),
                signing_string.encode('utf-8'),
                hashlib.sha256
            ).digest()
            expected_signature = base64.b64encode(expected_signature_bytes).decode('utf-8')
        except Exception:
            raise Forbidden()

        if not hmac.compare_digest(received_signature, expected_signature):
            raise Forbidden()
