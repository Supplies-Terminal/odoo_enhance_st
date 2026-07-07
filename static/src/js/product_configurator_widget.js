odoo.define("odoo_enhance_st.product_configurator", function (require) {
  var ProductConfiguratorWidget = require("sale.product_configurator");

  ProductConfiguratorWidget.include({
    _onProductChange: function (event, divId) {
      console.log("_onProductChange", event, divId);
      // 调用父类的_onProductChange方法
      var result = this._super.apply(this, arguments);

      var $row = $("tr[data-id='" + divId + "']"); // 获取到行
      var textareaDiv = $row.find("textarea[name='name']");
      if (textareaDiv != null || textareaDiv != undefined) {
        var textareaValue = textareaDiv.val(); // 获取textarea的值
        console.log(textareaValue);
        var trimmedName = textareaValue
          .split(" >> ")[0]
          .split("*")[0]
          .trim()
          .replace(/ \/ /g, "\n");
        textareaDiv.val(trimmedName);
      }
      return result;
    },
  });
});
