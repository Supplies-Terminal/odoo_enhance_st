# -*- coding: UTF-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = "sale.order"

    date_place = fields.Datetime(string='Place Date', required=False, readonly=True, index=True, copy=False, help="The date customers submit the quotation")

    quantity_counts = fields.Char(string='Quantity Counts', compute='_compute_quantity_counts', store=False)

    def action_confirm(self):
        _logger.info('******** action_confirm *********')
        _logger.info(self.name)
        _logger.info(self.state)
        
        # 检查前置条件
        invoices = self.env['account.move'].search([
            ('company_id', '=', self.company_id.id),
            ('invoice_user_id', '=', 2),
            ('payment_reference', '=', 'SO_SEQUENCE'),
        ], order='name desc')

        _logger.info(invoices)
        if not invoices or len(invoices) <2:
            raise UserError('No SO_SEQUENCE found in invoices (at least 2)')

        # 订单确认之后置换为invoice number
        result = super(SaleOrder, self).action_confirm()

        invoice = invoices[1]
        _logger.info(invoice.name)
        # invoiceName = invoice._get_last_sequence(lock=False)
        invoice.button_draft()
        invoice.write({
            'name': 'draft',
            'date': self.
        })
        _logger.info(invoice.name)
        invoice._set_next_sequence()
        _logger.info(invoice.name)
        # 根据销售订单的序列生成编号
        self.write({
            'name': invoice.name
        });

        return result

    @api.depends('order_line')
    def _compute_quantity_counts(self):
        for rec in self:
            results = []
            for line in rec.order_line:
                if line.product_qty>0:
                    if line.secondary_uom_enabled:
                        fres = list(filter(lambda x: x['uom_name'].lower()==line.secondary_uom_name.lower(), results))
                        if fres:
                            fres[0]['qty'] = fres[0]['qty'] + line.secondary_qty
                        else:
                            results.append({
                                'uom_name': line.secondary_uom_name,
                                'qty': line.secondary_qty
                                })
                    else:
                        fres = list(filter(lambda x: x['uom_name'].lower()==line.product_uom.name.lower(), results))
                        if fres:
                            fres[0]['qty'] = fres[0]['qty'] + line.product_qty
                        else:
                            results.append({
                                'uom_name': line.product_uom.name,
                                'qty': line.product_qty
                                })

            resultString = []
            for line in results:
                if line['qty'] > 1:
                    resultString.append(str(line['qty']) + " " + line['uom_name'] + "s")
                elif line['qty'] > 0:
                    resultString.append(str(line['qty']) + " " + line['uom_name'])
            
            if resultString:
                rec.quantity_counts = 'Quantity Counts: ' + ('; '.join(resultString))
            else:
                rec.quantity_counts = ''
