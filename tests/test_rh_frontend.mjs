import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source = fs.readFileSync(new URL('../web/feihou_easy_h3_ui.js', import.meta.url), 'utf8');
const scope = vm.createContext({ NODE_CLASS: 'FeiHouEasyH3RH', LOADER_CLASS: 'FeiHouEasyH3RHLoader', ADAPTER_CLASS: 'FeiHouEasyH3RHModelAdapter', OUTPUT_CLASS: 'FeiHouEasyH3RHOutput', DURATION_CROP_CLASS: 'FeiHouEasyH3RHDurationCrop', TEXT: {} });
vm.runInContext(source.slice(source.indexOf('function nodeMatchesClass('), source.indexOf('function canonicalOption(')), scope);
assert.ok(!/__h3Easy\w*Installed|__h3MediaSource\w*Installed/.test(source));
class RH {}
class Standard {}
class MiniMax {}
RH.prototype.__feihouRHH3EasyNodeInstalled = true;
Standard.prototype.__feihouStandardH3EasyNodeInstalled = true;
MiniMax.prototype.__h3EasyNodeInstalled = true;
const rh = Object.assign(new RH(), { id: 'rh', comfyClass: 'FeiHouEasyH3RH', title: 'renamed' });
const standard = Object.assign(new Standard(), { id: 'standard', comfyClass: 'FeiHouEasyH3', title: 'ComfyUI-FeiHou-Easy-H3-RH' });
const mini = Object.assign(new MiniMax(), { id: 'mini', comfyClass: 'MiniMaxH3Easy', title: 'ComfyUI-FeiHou-Easy-H3-RH' });
const foreignTarget = (n) => Boolean(n.constructor.prototype.__h3EasyNodeInstalled) || n.comfyClass === 'MiniMaxH3Easy';
assert.equal(scope.isTarget(rh), true);
assert.equal(scope.isTarget(standard), false);
assert.equal(scope.isTarget(mini), false);
assert.equal(foreignTarget(rh), false);
assert.equal(scope.isTarget({ title: 'ComfyUI-FeiHou-Easy-H3-RH' }), false);
for (const [name, check] of [['Loader', 'isLoader'], ['ModelAdapter', 'isAdapter'], ['Output', 'isOutput'], ['DurationCrop', 'isDurationCrop']]) {
    assert.equal(scope[check]({ comfyClass: 'FeiHouEasyH3RH' + name }), true);
    assert.equal(scope[check]({ comfyClass: 'FeiHouEasyH3' + name }), false);
}
// Minimal transport-wrapper simulation in both orders, not a full browser test.
for (const reverse of [false, true]) {
    const patches = [[scope.isTarget, 'rh.png'], [foreignTarget, 'mini.png']];
    if (reverse) patches.reverse();
    let queue = async () => ({ rh: {}, mini: {}, standard: { media_1: 'standard.png' } });
    for (const [target, filename] of patches) {
        const previous = queue;
        queue = async () => {
            const result = await previous();
            for (const node of [rh, mini, standard]) {
                if (!target(node)) continue;
                delete result[node.id].media_1;
                result[node.id].media_1 = filename;
            }
            return result;
        };
    }
    const result = await queue();
    assert.equal(result.rh.media_1, 'rh.png');
    assert.equal(result.mini.media_1, 'mini.png');
    assert.equal(result.standard.media_1, 'standard.png');
}
console.log('PASS: RH exact identity, standard/third-party exclusion, private flags, two transport orders');
