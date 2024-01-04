odoo.define("odoo_enhance_st.product_configurator", function (require) {
    var ProductConfiguratorWidget = require("sale.product_configurator");

    ProductConfiguratorWidget.include({
      _onProductChange: function (event) {
        // 调用父类的_onProductChange方法
        var result = this._super.apply(this, arguments);
        // 截取 ｜ 之后的内容
        if (this.$(".product_id").val()) {
          var productName = this.$(".product_id").select2("data")[0].text;
          var trimmedName = productName.split("｜")[0].trim();
          console.log(productName);
          console.log(trimmedName);
          this.$(".product_id").select2("data")[0].text = trimmedName;
        }
        return result;
      },
    });
});
