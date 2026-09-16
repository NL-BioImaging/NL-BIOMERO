// Requires an OMERO.web checkout: set OMERO_WEB_SOURCE, then npm install && npm test.
// Uses its actual jQuery, Chosen, and script dialog, not a mocked dropdown.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');

const source = process.env.OMERO_WEB_SOURCE || path.resolve(__dirname, '../../../omero-web');
const gateway = path.join(source, 'omeroweb/webgateway/static/3rdparty');
const original = path.join(source, 'omeroweb/webclient/templates/webclient/scripts/script_ui.html');
const override = path.join(__dirname, '../local_omeroweb_edits/script_ui.html');
const inlineScripts = (template) => [...template.matchAll(/<script type="text\/javascript">([\s\S]*?)<\/script>/g)]
    .map(match => match[1]).join('\n');

async function dialog(optionCount) {
    const options = Array.from({length: optionCount}, (_, index) =>
        `<option value="workflow-${index}">workflow-${index}</option>`).join('');
    const dom = new JSDOM(`<form id="script_form"><table><tr><td>
        <select id="uuid" name="Workflow_UUIDs">${options}</select>
        <a href="#" class="removeListSelect">[-]</a><a href="#" class="addListSelect">[+]</a>
        </td></tr></table></form>`, {runScripts: 'outside-only'});
    const window = dom.window;
    window.eval(fs.readFileSync(path.join(gateway, 'jquery-3.6.2.min.js'), 'utf8'));
    window.eval(fs.readFileSync(path.join(gateway, 'jquery.chosen-1.8.7/chosen.jquery.js'), 'utf8'));
    window.OME = {setupAjaxError() {}};
    window.$.fn.ajaxForm = window.$.fn.numbersOnly = function () { return this; };
    window.eval(inlineScripts(fs.readFileSync(original, 'utf8')));
    if (!process.env.BIOMERO_TEST_ORIGINAL_LIST_UI) {
        window.eval(inlineScripts(fs.readFileSync(override, 'utf8')));
    }
    await new Promise(resolve => window.$(resolve));
    return dom;
}

for (const optionCount of [5, 25]) {
    test(`list controls preserve visible selectors and submitted UUIDs (${optionCount} options)`, async () => {
        const dom = await dialog(optionCount);
        try {
            const $ = dom.window.$;
            $('select').val('workflow-2').trigger('chosen:updated');
            $('.addListSelect').trigger('click');
            assert.equal($('select').length, 2);
            if (optionCount > 20) {
                assert.equal($('.chosen-container').length, 2, 'each hidden select needs a visible widget');
                $('select').each(function () { assert.ok($(this).data('chosen')); });
            } else {
                $('select').each(function () { assert.notEqual(this.style.display, 'none'); });
            }
            $('select').last().val('workflow-3').trigger('chosen:updated');
            assert.deepEqual(new dom.window.FormData($('#script_form')[0]).getAll('Workflow_UUIDs'),
                ['workflow-2', 'workflow-3']);
            $('.removeListSelect').trigger('click');
            assert.equal($('select').length, 1);
            assert.equal($('.chosen-container').length, optionCount > 20 ? 1 : 0);
            assert.deepEqual(new dom.window.FormData($('#script_form')[0]).getAll('Workflow_UUIDs'),
                ['workflow-2']);
            $('.removeListSelect').trigger('click');
            assert.equal($('select').length, 1, 'the last selector remains available');
            for (let index = 0; index < 4; index++) $('.addListSelect').trigger('click');
            if (optionCount > 20) assert.equal($('.chosen-container').length, 5);
            const ids = $('[id]').map(function () { return this.id; }).get();
            assert.equal(new Set(ids).size, ids.length, 'clones must not duplicate DOM IDs');
            for (let index = 0; index < 4; index++) $('.removeListSelect').trigger('click');
            assert.equal($('select').length, 1);
            assert.equal($('.chosen-container').length, optionCount > 20 ? 1 : 0);
        } finally {
            dom.window.close();
        }
    });
}
