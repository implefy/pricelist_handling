from odoo import models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def action_open_price_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Manage Prices',
            'res_model': 'pricelist.price.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_tmpl_id': self.id,
            },
        }
