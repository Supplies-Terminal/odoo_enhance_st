# -*- coding: UTF-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = "sale.order"

    date_place = fields.Datetime(string='Place Date', required=False, readonly=True, index=True, copy=False, default=fields.Datetime.now, help="The date customers submit the quotation")

    quantity_counts = fields.Char(string='Quantity Counts', compute='_compute_quantity_counts', store=False)

    @api.depends('order_line')
    def _compute_quantity_counts(self):
        for rec in self:
            results = []
            for line in rec.order_line:
                if line.product_qty>0:
                    fres = filter(lambda x: x.uom_id==line.product_uom.id, results)
                    if fres:
                        fres[0].qty = fres[0].qty + line.product_qty
                    else:
                        results.append({
                            uom_id: line.product_uom.id,
                            uom_name: line.product_uom.name,
                            qty: line.product_qty
                            })


            resultString = []
            for line in results:
                if line.qty > 1:
                    resultString.append(line.qty + " " + line.uom_name + "s")
                else if line.qty > 0:
                    resultString.append(line.qty + " " + line.uom_name)
            
            rec.quantity_counts = (' '.join(resultString))
