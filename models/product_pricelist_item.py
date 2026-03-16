from odoo import api, fields, models


class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    discount_fixed_price = fields.Float(
        string="Fixed Price (Discounted)",
        digits='Product Price',
    )

    @api.onchange('discount_fixed_price', 'product_tmpl_id', 'product_id')
    def _onchange_discount_fixed_price(self):
        for item in self:
            if not item.discount_fixed_price:
                if not item.price_discount:
                    continue
                item.price_discount = 0
                continue

            product = item.product_id or item.product_tmpl_id
            if not product:
                continue

            base_price = self._get_base_price(item, product)
            if not base_price:
                continue

            item.compute_price = 'formula'
            item.price_discount = ((base_price - item.discount_fixed_price) / base_price) * 100

    def _get_base_price(self, item, product):
        """Resolve the base price according to the rule's base setting."""
        pricelist_currency = item.currency_id
        product_currency = product.currency_id

        if item.base == 'list_price':
            price = product.list_price
        elif item.base == 'standard_price':
            price = product.standard_price
        elif item.base == 'pricelist' and item.base_pricelist_id:
            price = item.base_pricelist_id._get_product_price(
                product, 1.0, currency=pricelist_currency,
            )
            # _get_product_price already returns in pricelist currency
            return price
        else:
            price = product.list_price

        if not price:
            return 0.0

        # Convert to pricelist currency if needed
        if product_currency and pricelist_currency and product_currency != pricelist_currency:
            price = product_currency._convert(
                price, pricelist_currency,
                item.env.company, fields.Date.context_today(item),
            )
        return price
