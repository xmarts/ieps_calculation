# -*- coding: utf-8 -*-
{
    'name': "Calculo de IEPS",

    'summary': """
        Calculo de IEPS en Facturacion y Ventas""",

    'description': """
        Reconfiguracion para calculo de IEPS
    """,

    'author': "Xmarts",
    'website': "https://www.xmarts.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'account',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','sale','account'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/res_partner.xml',
        #'reports/report_ieps.xml'
    ],
}