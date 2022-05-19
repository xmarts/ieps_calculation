# -*- coding: utf-8 -*-
{
    'name': "Calculo de IEPS",
    'summary': """Calculo de IEPS en Facturacion y Ventas""",
    'description': """Reconfiguracion para calculo de IEPS""",
    'author': "Xmarts",
    'contributors': "pablo.osorio@xmarts.com, victoralonso@xmarts.com, javier.hilario@xmarts.com",
    'website': "http://www.xmarts.com",
    'category': 'account',
    'version': '15.0.1.0.0',
    'depends': ['base', 'sale', 'account'],
    'data': [
        # 'security/ir.model.access.csv',
        'views/inherit_res_partner_views.xml',
        # 'views/views.xml',
        'views/inherit_account_tax_views.xml',
        'views/inherit_account_tax_group_views.xml',
        'views/cfdi.xml',
        # 'reports/report_ieps.xml'
        'reports/inherit_report_invoice_document_template.xml'
    ],
}
