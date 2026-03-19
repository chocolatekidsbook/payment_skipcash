# Part of Odoo. See LICENSE file for full copyright and licensing details.

# The currencies supported by skipcash, in ISO 4217 format.
# See https://skipcash.com/us/support/general/what-are-the-currencies-accepted-on-skipcash.
# Last website update: June 2022.
# Last seen online: 24 November 2022.
SUPPORTED_CURRENCIES = [
   'QAR'
]

# Mapping of transaction states to skipcash payment statuses.
PAYMENT_STATUS_MAPPING = {
    'pending': ['pending', 'pending auth'],
    'done': ['successful','paid'],
    'cancel': ['cancelled'],
    'error': ['failed'],
}

# The codes of the payment methods to activate when skipcash is activated.
DEFAULT_PAYMENT_METHOD_CODES = {
    # Primary payment methods.
    'card',
    'mpesa',
    # Brand payment methods.
    'visa',
    'mastercard',
    'amex',
    'discover',
}

PAYMENT_METHODS_MAPPING = {
    'bank_transfer': 'banktransfer',
}
