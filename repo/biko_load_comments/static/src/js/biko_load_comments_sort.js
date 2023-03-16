odoo.define('biko_load_comments.SortedMessages', function (require) {
    "use strict";
        const components = {
            ThreadCache: require("mail/static/src/models/thread_cache/thread_cache.js")
        };
    const {patch}= require("web.utils");
    patch(
        components.ThreadCache,
        "biko_load_comments/static/src/js/biko_load_comments_sort.js",
        {
            _computeOrderedMessages() {
              return [['replace', this.messages.sort((m1, m2) => m1.date < m2.date ? -1 : 1)]];
            }
        }
    );


});