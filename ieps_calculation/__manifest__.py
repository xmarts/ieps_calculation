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
        'views/res_partner.xml',
        'views/views.xml',
        'views/account_tax.xml',
        'views/cfdi.xml',
        # 'reports/report_ieps.xml'
        'reports/inherit_report_invoice_document_template.xml'
    ],
}
