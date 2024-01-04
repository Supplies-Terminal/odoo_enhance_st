odoo.define("odoo_enhance_st.product_configurator", function (require) {
    "use strict";

    var ProductConfiguratorWidget = require("sale.product_configurator");

    ProductConfiguratorWidget.include({
      _onProductChange: function (event) {
        // 调用父类的_onProductChange方法
        this._super.apply(this, arguments);
        // 截取 * 之后的内容
        if (this.$(".product_id").val()) {
          var productName = this.$(".product_id").select2("data")[0].text;
          var trimmedName = productName.split("*")[0].trim();
          this.$(".product_id").select2("data")[0].text = trimmedName;
        }
      },
    });
});
