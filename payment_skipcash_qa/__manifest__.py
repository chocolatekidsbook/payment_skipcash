# -*- coding: utf-8 -*-
{
    'name': 'SkipCash Payment Gateway',
    'version': '19.0.1.0',
    'category': 'Accounting/Payment Providers',
    'sequence': 1,
    'summary': 'Odoo SkipCash Payment Gateway',
    'description': 'Odoo SkipCash Payment Gateway for Qatar',
    'author': 'Manok',
    'website': '',
    'depends': ['base','payment'],
    'data': [
        'views/payment_skipcash_templates.xml',
        'views/payment_provider_views.xml',
        'data/payment_provider_data.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
    'price': 150,
    'currency': 'USD',
    'external_dependencies': {
        "python": ["skipcash"],
    },
}
