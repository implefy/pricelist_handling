from odoo import fields, models


class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    price_type = fields.Selection(
        [('base', 'Base'), ('discount', 'Discounted')],
        string='Wizard Price Type',
        help='Controls how this pricelist appears in the Manage Prices wizard. '
             '"Base" shows the Fixed Price column. '
             '"Discounted" shows the Discount Price column. '
             'Leave empty to exclude from the wizard.',
    )
