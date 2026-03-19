# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from werkzeug.urls import url_join

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.const import REPORT_REASONS_MAPPING
from odoo.addons.payment_skipcash_qa import const
from skipcash.client import SkipCash


_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('skipcash', "Skipcash")], ondelete={'skipcash': 'set default'}
    )

    skipcash_key_id = fields.Char('Skipcash Key ID', required_if_provider='skipcash')
    skipcash_webhook_key = fields.Char('Skipcash WebHook Key', required_if_provider='skipcash')
    skipcash_secret = fields.Char('Skipcash Secret', required_if_provider='skipcash')
    skipcash_client_id = fields.Char('Skipcash Client ID', required_if_provider='skipcash')

    #=== COMPUTE METHODS ===#

    def _compute_feature_support_fields(self):
        """ Override of `payment` to enable additional features. """
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'skipcash').update({
            'support_tokenization': True,
        })

    def skipcash_get(self):
        """ Return an authenticated SkipCash client instance.
        """
        try:
            return SkipCash(
                client_id=self.skipcash_client_id,
                key_id=self.skipcash_key_id,
                key_secret=self.skipcash_secret,
                webhook_secret=self.skipcash_webhook_key,
                use_sandbox=self.state == 'test',
            )
        except Exception as e:
            _logger.error("SkipCash client initialisation failed: %s", e)

    # === BUSINESS METHODS ===#

    @api.model
    def _get_compatible_providers(self, *args, is_validation=False, report=None, **kwargs):
        """ Override of `payment` to filter out Skipcash providers for validation operations. """
        providers = super()._get_compatible_providers(
            *args, is_validation=is_validation, report=report, **kwargs
        )

        if is_validation:
            unfiltered_providers = providers
            providers = providers.filtered(lambda p: p.code != 'skipcash')
            payment_utils.add_to_report(
                report,
                unfiltered_providers - providers,
                available=False,
                reason=REPORT_REASONS_MAPPING['validation_not_supported'],
            )

        return providers

    def _get_supported_currencies(self):
        """ Override of `payment` to return the supported currencies. """
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'skipcash':
            supported_currencies = supported_currencies.filtered(
                lambda c: c.name in const.SUPPORTED_CURRENCIES
            )
        return supported_currencies

    def _get_default_payment_method_codes(self):
        """ Override of `payment` to return the default payment method codes. """
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'skipcash':
            return default_codes
        return const.DEFAULT_PAYMENT_METHOD_CODES
