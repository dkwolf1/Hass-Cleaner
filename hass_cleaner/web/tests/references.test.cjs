const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const panels = new Map();
const element = () => ({dataset: {}, isConnected: true, innerHTML: '', textContent: '',
  children: [], append(...items) { this.children.push(...items); }, addEventListener() {}});
const context = {
  window: {HassCleanerI18n: {locale: 'en'}, addEventListener() {}},
  document: {querySelector: selector => panels.get(selector) || null, createElement: element},
  URLSearchParams, console,
};
const app = fs.readFileSync(path.join(__dirname, '../assets/app.js'), 'utf8');
vm.runInNewContext(app.replace(/init\(\);\s*$/, ''), context);
const row = {source_name: '<img src=x onerror=alert(1)>', source_id: 'automation.test',
  target_id: 'sensor.test', target_type: 'entity', location: '$.actions[0].entity_id', missing: true};
assert.ok(context.referenceRows([row]).includes('&lt;img'));
assert.ok(!context.referenceRows([row]).includes('<img'));
assert.match(context.referenceRows([row]), /missing/);
assert.match(context.referenceRows([{...row, missing: false, verification: 'unavailable'}]), /verification unavailable/);
assert.match(context.referenceWarning(), /does not mean removal is safe/);
context.window.HassCleanerI18n.locale = 'nl';
assert.match(context.referenceRows([row]), /ontbreekt/);
assert.match(context.referenceWarning(), /betekent niet/);
assert.match(context.referenceStatus('partial'), /Gedeeltelijke/);
context.window.HassCleanerI18n.locale = 'en';

(async () => {
  vm.runInNewContext('state.scan = {id: "first"}', context);
  let requested;
  context.api = async url => { requested = url; return {items: [row], total: 250, has_more: true,
    status: 'partial', checked_at: '2026-09-06T12:00:00Z', sources: []}; };
  const panel = element();
  await context.loadReferencePanel(panel, {entity_id: 'sensor.a&b'});
  assert.match(requested, /entity_id=sensor.a%26b/);
  assert.match(requested, /limit=100/);
  assert.match(panel.innerHTML, /250 matching references/);
  assert.equal(panel.children.length, 2); // usage summary and next-page control

  let resolve;
  context.api = () => new Promise(done => { resolve = done; });
  const pending = context.loadReferencePanel(panel);
  vm.runInNewContext('state.scan = {id: "second"}', context);
  resolve({items: [row], total: 999, status: 'completed'});
  await pending;
  assert.ok(!panel.innerHTML.includes('999')); // old scan must not replace new data

  context.api = async () => { throw new Error('offline'); };
  await context.loadReferencePanel(panel);
  assert.match(panel.textContent, /unavailable: offline/);
  const planPanel = element();
  panels.set('#plan-references', planPanel);
  context.renderPlanReferences({status: 'completed', references: [row], count: 150});
  assert.match(planPanel.innerHTML, /First 100 shown/);
  context.window.HassCleanerI18n.locale = 'nl';
  context.renderPlanReferences({status: 'unavailable', references: [], count: 0});
  assert.match(planPanel.innerHTML, /niet beschikbaar/);
  assert.match(planPanel.innerHTML, /Controleer deze bronnen/);
  console.log('Reference UI regression checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
