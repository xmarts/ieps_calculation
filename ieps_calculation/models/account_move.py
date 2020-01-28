# -*- coding: utf-8 -*-
from odoo import api, exceptions, fields, models, _

class AccountMoveLine(models.Model):
	_inherit = "account.move.line"

	@api.onchange("product_id")
	def _onchange_product_ieps(self):
		if self.type in ('out_invoice', 'out_refund'):
			amount_ieps = 0
			taxs = self.product_id.taxes_id.filtered(lambda r: not self.company_id or r.company_id == self.company_id)
			lista = []
			for x in taxs:
				ieps = False
				for z in x.tag_ids:
					if z.name == 'IEPS':
						ieps = True
				if ieps == True:
					amount_ieps += x.amount
			self.credit = (self.product_id.lst_price - amount_ieps) * self.quantity