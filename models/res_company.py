# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models, tools

class ResCompany(models.Model):
    _inherit = "res.company"

    # service_def = fields.Text(string='App Service Def');

