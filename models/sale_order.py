# -*- coding: UTF-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models, fields, api
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = "sale.order"

    date_place = fields.Datetime(string='Place Date', required=False, readonly=True, index=True, copy=False, help="The date customers submit the quotation")

    quantity_counts = fields.Char(string='Quantity Counts', compute='_compute_quantity_counts', store=False)

    CUSTOM_FIELD_STATES = {
        state: [('readonly', False)]
        for state in {'sale', 'done', 'cancel'}
    }
    
    date_order = fields.Datetime(
        string="Order Date",
        states=CUSTOM_FIELD_STATES,
        copy=False, 
        required=True,
        help="Creation date of draft/sent orders,\nConfirmation date of "
             "confirmed orders.")
    
    def action_confirm(self):
        _logger.info('******** action_confirm *********')
        
        # 检查前置条件
        invoices = self.env['account.move'].search([
            ('company_id', '=', self.company_id.id),
            ('invoice_user_id', '=', 2),
            ('payment_reference', '=', 'SO_SEQUENCE'),
        ], order='name desc')

        _logger.info(invoices)
        if not invoices or len(invoices) < 2:
            raise UserError('No SO_SEQUENCE found in invoices (at least 2)')

        # 订单确认之后置换为invoice number
        result = super(SaleOrder, self).action_confirm()

        invoice = invoices[1]
        _logger.info(invoice.name)
        # invoiceName = invoice._get_last_sequence(lock=False)
        invoice.button_draft()
        invoice.write({
            'name': 'draft',
            'date': self.date_order
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
    
    def _create_invoices(self, grouped=False, final=False, date=None):
        _logger.info('******** _create_invoices *********')
        _logger.info(self.name)
        
        invoices = super(SaleOrder, self)._create_invoices(grouped, final, date)
        _logger.info(invoices)
        if len(invoices) == 1:
            invoice = invoices[0]
            # 先释放原来的invoice号码
            oldInvoices = self.env['account.move'].search([
                ('company_id', '=', self.company_id.id),
                ('invoice_user_id', '=', 2),
                ('name', '=', self.name),
            ])
            _logger.info(oldInvoices)

            if oldInvoices:
                for oldInv in oldInvoices:
                    oldInv.write({
                        'name': '/'
                    });

            # 检查是否已经创建过一次invoice
            currentInvoices = self.env['account.move'].search([
                ('company_id', '=', self.company_id.id),
                ('name', '=', self.name),
            ])
            
            if currentInvoices:
                invoice.write({
                    'name': self.name + '-' + (len(currentInvoices) + 1),
                    'invoice_date': self.date_order
                })
            else:
                invoice.write({
                    'name': self.name
                })
        else:
            for index, inv in enumerate(invoices):
                inv.write({
                    'name': self.name + '-' + (index+1),
                    'invoice_date': self.date_order
                });
                
        return invoices
