# -*- coding: utf-8 -*-
from odoo import api, exceptions, fields, models, _

class PosOrderLine(models.Model):
	_inherit = 'pos.order.line'

	@api.model
	def create(self, vals):
		rec = super(PosOrderLine, self).create(vals)
		if rec.order_id.partner_id:
			if rec.order_id.partner_id.show_ieps != True:
				taxs = rec.tax_ids
				lista = []
				for x in taxs:
					ieps_t = False
					for t in x.tag_ids:
						if t.name == "IEPS":
							ieps_t = True
					if ieps_t ==  False:
						lista.append(x.id)
				rec.update({"tax_ids" : [(6,0,lista)]})
				rec.update({"tax_ids_after_fiscal_position" : [(6,0,lista)]})
				# rec.tax_ids_after_fiscal_position = [(6,0,lista)]
				return rec
			else:
				return rec
		else:
			return rec