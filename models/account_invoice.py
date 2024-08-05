# -*- coding: UTF-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api
from pytz import timezone
from datetime import datetime, time
import pytz

import logging
_logger = logging.getLogger(__name__)


class AccountInvoice(models.Model):
    _inherit = 'account.move'

    def _set_next_sequence(self):
        if not self.company_id.private_contact_only and not self.company_id.private_product_only and not self.company_id.is_virtual:
            _logger.info("销售公司使用virtual company序列号")
            # 检查前置条件
            invoices = self.env['account.move'].sudo().search([
                ('company_id.is_virtual', '=', True),
                ('invoice_user_id', '=', 2),
                ('payment_reference', '=', 'SO_SEQUENCE'),
            ], order='name desc')
            
            if not invoices or len(invoices) < 2:
                raise UserError('No SO_SEQUENCE found for invoices (at least 2) in virtual company')

            toronto_timezone = pytz.timezone('America/Toronto')
            now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
            now_toronto = now_utc.astimezone(toronto_timezone)
        
            invoice = invoices[1]
            invoice.button_draft()
            invoice.write({
                'name': 'draft',
                'date': now_toronto
            })
            _logger.info(invoice.name)
            invoice._set_next_sequence()

            # 使用虚拟公司生成的序列号
            self.name = invoice.name
            _logger.info(self.name)
        else:
            _logger.info("非销售公司，使用自己的序列号")
            super(AccountInvoice, self)._set_next_sequence()
            
    def _prepare_invoice_line_from_po_line(self, line):
        res = super(AccountInvoice,
                    self)._prepare_invoice_line_from_po_line(line)
        res.update({
            'secondary_qty': line.secondary_qty,
            'secondary_uom': line.secondary_uom.id,
        })
        return res

    def action_post(self):
        # 调用父类的 action_post 方法
        super(AccountInvoice, self).action_post()

        # 对于每个发票，将其日期设置为对应销售订单的订单日期
        for record in self:
            # 检查是否存在源销售订单
            if record.invoice_origin:
                sale_order = self.env['sale.order'].search([('name', '=', record.invoice_origin)], limit=1)
                if sale_order and sale_order.date_order:
                    # 将发票日期设置为销售订单的日期
                    # 考虑时区转换
                    # user_tz = self.env.user.tz or self.env.context.get('tz')
                    # if user_tz:
                    #     local = timezone(user_tz)
                    #     local_dt = local.localize(fields.Datetime.from_string(sale_order.date_order), is_dst=None)
                    #     utc_dt = local_dt.astimezone(timezone('UTC'))
                    #     record.write({
                    #         'invoice_date': utc_dt,
                    #         'invoice_date_due': utc_dt,
                    #     })
                    # else:
                    #     # 如果无法确定时区，则直接使用订单日期
                    
                    # UTC时间转换为多伦多时间
                    record.write({
                        'invoice_date': sale_order.date_order.astimezone(timezone('america/toronto')).date(),
                        'invoice_date_due': sale_order.date_order.astimezone(timezone('america/toronto')).date(),
                    })

class AccountInvoiceLine(models.Model):
    _inherit = "account.move.line"

    secondary_qty = fields.Float("Secondary QTY", digits='Product Unit of Measure')
    secondary_uom_id = fields.Many2one("uom.uom", 'Secondary UoM', compute='_compute_secondary_uom_id', store=True)
    secondary_uom_name = fields.Char("Secondary Unit", compute='_compute_secondary_uom_name', store=True)
    secondary_uom_enabled = fields.Boolean("Secondary UoM Enabled?", compute='_compute_secondary_uom_enabled', store=True)
    secondary_uom_rate = fields.Float( "Secondary Unit Rate", compute='_compute_secondary_uom_rate', store=True)
    secondary_uom_desc = fields.Char(string='Secondary Unit Desc', compute='_compute_secondary_uom_desc', store=True)
    description_with_counts = fields.Char(string='Item Description', compute='_compute_description_with_counts', store=True)

    @api.depends('product_id')
    def _compute_secondary_uom_id(self):
        for rec in self:
            if rec.product_id.secondary_uom_enabled and rec.product_id.secondary_uom_id:
                rec.secondary_uom_id = rec.product_id.secondary_uom_id.id
            # else:
            #     rec.secondary_uom_id = 

    @api.depends('product_id')
    def _compute_secondary_uom_name(self):
        for rec in self:
            if rec.product_id.secondary_uom_enabled:
                rec.secondary_uom_name = rec.product_id.secondary_uom_name
            else:
                rec.secondary_uom_name = ""

    @api.depends('product_id')
    def _compute_secondary_uom_rate(self):
        for rec in self:
            if rec.product_id.secondary_uom_enabled:
                rec.secondary_uom_rate = rec.product_id.secondary_uom_rate
            else:
                rec.secondary_uom_rate = 0.00

    @api.depends('product_id')
    def _compute_secondary_uom_enabled(self):
        for rec in self:
            rec.secondary_uom_enabled = rec.product_id.secondary_uom_enabled

                
    @api.depends('secondary_uom_enabled', 'product_uom_id', 'secondary_uom_id', 'secondary_uom_rate')
    def _compute_secondary_uom_desc(self):
        for rec in self:
            if rec.secondary_uom_enabled:
                rec.secondary_uom_desc = "%s (%s %s)" % (rec.secondary_uom_name, rec.secondary_uom_rate, rec.product_uom_id.name)
            else:
                rec.secondary_uom_desc = ""

    @api.depends('secondary_uom_enabled', 'secondary_qty')
    def _compute_description_with_counts(self):
        for rec in self:
            if rec.secondary_uom_enabled:
                rec.description_with_counts = "%s (%s %s)" % (rec.name, rec.secondary_qty, rec.secondary_uom_name)
            else:
                rec.description_with_counts = rec.name

    @api.onchange('secondary_qty')
    def onchange_secondary_qty(self):
        if self and self.secondary_uom_enabled and self.product_uom_id:
            if self.quantity:
                self.quantity = self.secondary_qty * self.secondary_uom_rate
            else:
                self.quantity = 0

    @api.onchange('product_id')
    def onchange_secondary_uom(self):
        if self:
            for rec in self:
                if rec.product_id:
                    if rec.product_id.secondary_uom_enabled and rec.product_id.secondary_uom_id:
                        rec.secondary_uom_id = rec.product_id.secondary_uom_id.id
                        rec.quantity = rec.secondary_qty * rec.product_id.secondary_uom_rate
                    else:
                        rec.secondary_qty = 0.0
                        rec.quantity = 0.0
                else:
                    rec.secondary_qty = 0.0
                    rec.quantity = 0.0
               