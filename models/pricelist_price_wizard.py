from odoo import api, fields, models


class PricelistPriceWizard(models.TransientModel):
    _name = 'pricelist.price.wizard'
    _description = 'Pricelist Price Wizard'

    product_tmpl_id = fields.Many2one(
        'product.template', string='Product Template', readonly=True,
    )
    line_ids = fields.One2many(
        'pricelist.price.wizard.line', 'wizard_id', string='Price Lines',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        tmpl_id = self.env.context.get('default_product_tmpl_id')
        if not tmpl_id:
            return res

        template = self.env['product.template'].browse(tmpl_id)
        variants = template.product_variant_ids
        if not variants:
            return res

        base_pricelists = self.env['product.pricelist'].search(
            [('price_type', '=', 'base')], order='currency_id',
        )
        discount_pricelists = self.env['product.pricelist'].search(
            [('price_type', '=', 'discount')], order='currency_id',
        )
        if not base_pricelists and not discount_pricelists:
            return res

        # Group pricelists by currency
        # {currency_id: {'base': pricelist, 'discount': pricelist}}
        currency_map = {}
        for pl in base_pricelists:
            currency_map.setdefault(pl.currency_id.id, {})['base'] = pl
        for pl in discount_pricelists:
            currency_map.setdefault(pl.currency_id.id, {})['discount'] = pl

        # Build lookup: (product_id, pricelist_id) -> pricelist.item
        all_pricelists = base_pricelists | discount_pricelists
        existing_items = self.env['product.pricelist.item'].search([
            ('pricelist_id', 'in', all_pricelists.ids),
            '|',
            ('product_tmpl_id', '=', tmpl_id),
            ('product_id', 'in', variants.ids),
        ])
        variant_item_map = {}
        tmpl_item_map = {}
        for item in existing_items:
            if item.product_id:
                variant_item_map[(item.product_id.id, item.pricelist_id.id)] = item
            else:
                tmpl_item_map.setdefault(item.pricelist_id.id, item)

        def find_item(variant, pricelist):
            if not pricelist:
                return None
            item = variant_item_map.get((variant.id, pricelist.id))
            if not item:
                item = tmpl_item_map.get(pricelist.id)
            return item

        currencies = self.env['res.currency'].browse(sorted(currency_map.keys()))
        lines = []
        for variant in variants.sorted(key=lambda v: v.display_name):
            for currency in currencies:
                pl_pair = currency_map[currency.id]
                base_pl = pl_pair.get('base')
                disc_pl = pl_pair.get('discount')
                base_item = find_item(variant, base_pl)
                disc_item = find_item(variant, disc_pl)

                lines.append((0, 0, {
                    'product_id': variant.id,
                    'currency_id': currency.id,
                    'base_pricelist_id': base_pl.id if base_pl else False,
                    'discount_pricelist_id': disc_pl.id if disc_pl else False,
                    'fixed_price': base_item.fixed_price if base_item else 0.0,
                    'discount_fixed_price': disc_item.discount_fixed_price if disc_item else 0.0,
                    'base_item_id': base_item.id if base_item else False,
                    'discount_item_id': disc_item.id if disc_item else False,
                }))

        res['product_tmpl_id'] = tmpl_id
        res['line_ids'] = lines
        return res

    def action_apply(self):
        self.ensure_one()
        PricelistItem = self.env['product.pricelist.item']
        single_variant = len(self.product_tmpl_id.product_variant_ids) == 1

        for line in self.line_ids:
            # --- Base price ---
            if line.base_pricelist_id:
                self._apply_base_price(line, PricelistItem, single_variant)
            # --- Discount price ---
            if line.discount_pricelist_id:
                self._apply_discount_price(line, PricelistItem, single_variant)

        return {'type': 'ir.actions.act_window_close'}

    def _apply_base_price(self, line, PricelistItem, single_variant):
        if line.base_item_id:
            if line.fixed_price != line.base_item_id.fixed_price:
                line.base_item_id.fixed_price = line.fixed_price
        elif line.fixed_price:
            vals = {
                'pricelist_id': line.base_pricelist_id.id,
                'product_tmpl_id': self.product_tmpl_id.id,
                'compute_price': 'fixed',
                'fixed_price': line.fixed_price,
            }
            if single_variant:
                vals['applied_on'] = '1_product'
            else:
                vals['applied_on'] = '0_product_variant'
                vals['product_id'] = line.product_id.id
            PricelistItem.create(vals)

    def _apply_discount_price(self, line, PricelistItem, single_variant):
        if line.discount_item_id:
            if line.discount_fixed_price != line.discount_item_id.discount_fixed_price:
                line.discount_item_id.discount_fixed_price = line.discount_fixed_price
                line.discount_item_id._onchange_discount_fixed_price()
        elif line.discount_fixed_price:
            vals = {
                'pricelist_id': line.discount_pricelist_id.id,
                'product_tmpl_id': self.product_tmpl_id.id,
                'compute_price': 'fixed',
                'fixed_price': line.discount_fixed_price,
            }
            if single_variant:
                vals['applied_on'] = '1_product'
            else:
                vals['applied_on'] = '0_product_variant'
                vals['product_id'] = line.product_id.id
            new_item = PricelistItem.create(vals)
            new_item.discount_fixed_price = line.discount_fixed_price
            new_item._onchange_discount_fixed_price()


class PricelistPriceWizardLine(models.TransientModel):
    _name = 'pricelist.price.wizard.line'
    _description = 'Pricelist Price Wizard Line'

    wizard_id = fields.Many2one(
        'pricelist.price.wizard', string='Wizard', required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product', string='Variant', readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency', readonly=True,
    )
    base_pricelist_id = fields.Many2one(
        'product.pricelist', string='Base Pricelist',
    )
    discount_pricelist_id = fields.Many2one(
        'product.pricelist', string='Discount Pricelist',
    )
    fixed_price = fields.Monetary(
        string='Price', currency_field='currency_id',
    )
    discount_fixed_price = fields.Float(
        string='Discount Price', digits='Product Price',
    )
    base_item_id = fields.Many2one(
        'product.pricelist.item', string='Base Item',
    )
    discount_item_id = fields.Many2one(
        'product.pricelist.item', string='Discount Item',
    )
