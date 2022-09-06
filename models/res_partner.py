# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models, tools

class Partner(models.Model):
    _inherit = "res.partner"

    @api.model
    def name_get(self):
        res = []
        for rec in self:
            if rec.ref:
                res.append((rec.id, "%s <br/>%s" % (rec.name, rec.ref)))
            else:
                res.append((rec.id, "%s" % rec.name))
        return res
