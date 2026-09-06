const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const textNode = value => ({nodeType: 3, nodeValue: value});
function element(children = [], attrs = {}, tagName = 'DIV') {
  const node = {nodeType: 1, tagName, childNodes: children,
    hasAttribute: name => name in attrs, getAttribute: name => attrs[name],
    setAttribute: (name, value) => { attrs[name] = value; }};
  children.forEach(child => { child.parentElement = node; });
  return node;
}
const dynamic = textNode('Nieuwe scan');
const label = element([], {'aria-label': 'Filter op status'});
const source = textNode('Nieuwe scan');
const code = element([source], {}, 'PRE');
const root = element([dynamic, label, code]);
let mutationCallback;
const context = {Node: {TEXT_NODE: 3, ELEMENT_NODE: 1}, navigator: {languages: ['en-GB', 'nl-NL']},
  document: {documentElement: root, body: root, addEventListener() {}},
  window: {dispatchEvent() {}}, CustomEvent: class {},
  MutationObserver: class {constructor(callback) {mutationCallback = callback;} disconnect() {} observe() {}}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../assets/i18n.js'), 'utf8'), context);
const i18n = context.window.HassCleanerI18n;
i18n.setPreference('auto');
assert.equal(i18n.locale, 'en');
assert.equal(dynamic.nodeValue, 'New scan');
assert.equal(label.getAttribute('aria-label'), 'Filter by state');
assert.equal(source.nodeValue, 'Nieuwe scan');
assert.equal(i18n.text('0 resultaten · 0 geselecteerd · jij beslist na advies en back-upkeuze'),
  '0 results · 0 selected · you decide after reviewing guidance and the backup choice');
assert.equal(i18n.text('2 apparaten en 4 entities. 1 registerafwijking voor eigen beoordeling.'),
  '2 devices and 4 entities. 1 registry anomaly for your review.');
dynamic.nodeValue = 'Instellingen';
label.setAttribute('aria-label', 'Zoek entiteiten');
mutationCallback([{type: 'characterData', target: dynamic}, {type: 'attributes', target: label}]);
assert.equal(dynamic.nodeValue, 'Settings');
assert.equal(label.getAttribute('aria-label'), 'Search entities');
i18n.setPreference('nl');
assert.equal(dynamic.nodeValue, 'Instellingen');
assert.equal(label.getAttribute('aria-label'), 'Zoek entiteiten');
i18n.setPreference('en');
assert.equal(dynamic.nodeValue, 'Settings');
context.navigator.languages = ['nl-NL', 'en-GB'];
i18n.setPreference('auto');
assert.equal(i18n.locale, 'nl');
context.navigator.languages = ['fr-FR'];
i18n.setPreference('auto');
assert.equal(i18n.locale, 'en');
assert.equal(i18n.text('sensor.my_identifier'), 'sensor.my_identifier');
console.log('i18n regression checks passed');
