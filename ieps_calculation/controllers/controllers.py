# -*- coding: utf-8 -*-
from odoo import http

# class IepsCalculation(http.Controller):
#     @http.route('/ieps_calculation/ieps_calculation/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/ieps_calculation/ieps_calculation/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('ieps_calculation.listing', {
#             'root': '/ieps_calculation/ieps_calculation',
#             'objects': http.request.env['ieps_calculation.ieps_calculation'].search([]),
#         })

#     @http.route('/ieps_calculation/ieps_calculation/objects/<model("ieps_calculation.ieps_calculation"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('ieps_calculation.object', {
#             'object': obj
#         })