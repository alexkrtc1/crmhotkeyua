odoo.define('biko_batch.ImportCommentsMenu', function (require) {
    "use strict";

    const FavoriteMenu = require('web.FavoriteMenu');
    const { useModel } = require('web.Model');

    const { Component } = owl;

    const core = require('web.core');
    const _t = core._t;

    /**
     * Import Records menu
     *
     * This component is used to import the records for particular model.
     */
    class ImportCommentsMenu extends Component {
        constructor() {
            super(...arguments);
            this.model = useModel('searchModel');
        }

        //---------------------------------------------------------------------
        // Handlers
        //---------------------------------------------------------------------

        /**
         * @private
         */
        importRecords() {
//            const action = {
//                type: 'ir.actions.client',
//                tag: 'import_comments',
//                params: {
//                    model: this.model.config.modelName,
//                    context: this.model.config.context,
//                }
//            };
//            this.trigger('do-action', {action: action});
            const action = {
                type: 'ir.actions.act_window',
                name: _t('Import comments'),
                res_model: 'biko.import.recs',
                view_mode: 'form',
                views: [[false, 'form']],
                target: 'new'
            };
            this.trigger('do-action', {action: action});
        }

        //---------------------------------------------------------------------
        // Static
        //---------------------------------------------------------------------

        /**
         * @param {Object} env
         * @returns {boolean}
         */
        static shouldBeDisplayed(env) {
            return env.view &&
                ['kanban', 'list'].includes(env.view.type) &&
                env.action.type === 'ir.actions.act_window' &&
                !env.device.isMobile &&
                !!JSON.parse(env.view.arch.attrs.import || '1') &&
                !!JSON.parse(env.view.arch.attrs.create || '1');
        }
    }

    ImportCommentsMenu.props = {};
    ImportCommentsMenu.template = "biko_batch.ImportCommentsMenu";

    FavoriteMenu.registry.add('biko-import-comments-menu', ImportCommentsMenu, 2);

    return ImportCommentsMenu;
});