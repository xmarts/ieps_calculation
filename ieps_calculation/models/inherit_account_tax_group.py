# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = "account.tax.group"

    ieps = fields.Boolean(string="Es IEPS.", default=False)
