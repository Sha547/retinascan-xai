import test from 'node:test';
import assert from 'node:assert/strict';
import graded from '../src/fixtures/analyse_graded.json' with { type: 'json' };
import abstained from '../src/fixtures/analyse_abstained.json' with { type: 'json' };
import retake from '../src/fixtures/analyse_retake.json' with { type: 'json' };
import pending from '../src/fixtures/cases_pending.json' with { type: 'json' };
import error415 from '../src/fixtures/error_415.json' with { type: 'json' };
let instance = 0;
async function api(search = '?demo=1') {
  globalThis.window = { location: { search } };
  return import(`../src/api.js?test=${instance++}`);
}

test('demo outcomes retain exact fixture predictions, quality and evidence', async () => {
  const a = await api();
  for (const [outcome, fixture] of Object.entries({ graded, abstained, retake })) {
    const c = await a.analyse(null, { outcome, patient_id: 'TEST', eye: 'right' });
    assert.deepEqual(c.prediction, fixture.prediction);
    assert.deepEqual(c.quality, fixture.quality);
    assert.deepEqual(c.evidence, fixture.evidence);
    assert.equal(c.recommendation, fixture.recommendation);
    assert.equal(c.patient_id, 'TEST');
    assert.equal(c.eye, 'right');
    assert.deepEqual(await a.getCase(c.case_id), c);
  }
});
test('queue order, accept/override history, filters and retake guard', async () => {
  const a = await api();
  assert.deepEqual(
    (await a.getCases()).cases.map((c) => c.case_id),
    pending.cases.map((c) => c.case_id),
  );
  const id = graded.case_id;
  const accepted = await a.postDecision(id, { action: 'accept', reviewer: 'Dr. Test', note: '' });
  assert.equal(accepted.final_grade, graded.prediction.grade);
  assert.equal(accepted.status, 'accepted');
  const updated = await a.postDecision(id, {
    action: 'override',
    final_grade: 3,
    reviewer: 'Dr. Test',
    note: 'Review note',
  });
  assert.equal(updated.status, 'overridden');
  assert.equal(updated.final_grade, 3);
  assert.equal(updated.decisions.length, 2);
  assert.equal(
    (await a.getCases()).cases.some((c) => c.case_id === id),
    false,
  );
  assert.equal((await a.getCases('reviewed')).cases.find((c) => c.case_id === id).final_grade, 3);
  assert.equal((await a.getCases('all')).cases.find((c) => c.case_id === id).status, 'overridden');
  await assert.rejects(a.postDecision(retake.case_id, { action: 'accept', reviewer: 'Dr. Test' }), {
    status: 409,
  });
  await assert.rejects(a.postDecision(id, { action: 'override', reviewer: 'Dr. Test' }), {
    status: 422,
  });
  await assert.rejects(a.postDecision(id, { action: 'accept', reviewer: ' ' }), { status: 422 });
});
test('summary-only fixtures never manufacture probabilities or evidence', async () => {
  const a = await api();
  for (const s of pending.cases.filter(
    (c) => ![graded.case_id, abstained.case_id].includes(c.case_id),
  )) {
    const c = await a.getCase(s.case_id);
    assert.equal(c.fixturePartial, true);
    assert.equal(c.prediction.probs, null);
    assert.equal(c.prediction.confidence, s.confidence);
    assert.equal(c.evidence, null);
    assert.equal(c.recommendation, null);
    assert.equal(
      (await a.postDecision(c.case_id, { action: 'accept', reviewer: 'Dr. Test' })).final_grade,
      s.grade,
    );
  }
});
test('unreachable health enables demo with a visible notice; HTTP errors stay errors', async () => {
  let a = await api('');
  globalThis.fetch = async () => {
    throw new TypeError('Network unavailable');
  };
  const connection = await a.initialiseApi();
  assert.equal(connection.demo, true);
  assert.match(connection.notice, /unreachable/);
  a = await api('');
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({
        error: { code: 'model_unavailable', message: 'Model unavailable, try again.' },
      }),
      { status: 503 },
    );
  await assert.rejects(a.initialiseApi(), {
    message: 'Model unavailable, try again.',
    status: 503,
  });
  assert.equal(a.isDemoMode(), false);
});
test('live multipart, JSON decisions, image endpoints and error envelopes', async () => {
  const a = await api('');
  const calls = [];
  globalThis.fetch = async (path, options) => {
    calls.push({ path, options });
    if (path.endsWith('/image') || path.endsWith('.jpg'))
      return new Response(new Blob(['image'], { type: 'image/png' }));
    return new Response(JSON.stringify(graded), { status: 201 });
  };
  const file = new File(['pixels'], 'scan.png', { type: 'image/png' });
  await a.analyse(file, { patient_id: 'TEST', eye: 'left' });
  assert.equal(calls[0].path, '/api/analyse');
  assert.equal(calls[0].options.body.get('image').name, 'scan.png');
  assert.equal(calls[0].options.body.get('patient_id'), 'TEST');
  assert.equal(calls[0].options.body.get('eye'), 'left');
  await a.getCases('reviewed');
  assert.match(calls.at(-1).path, /status=reviewed&limit=50/);
  await a.postDecision(graded.case_id, {
    action: 'override',
    reviewer: 'Dr. Test',
    final_grade: 4,
  });
  assert.equal(JSON.parse(calls.at(-1).options.body).final_grade, 4);
  assert.equal((await a.getCaseImage(graded.case_id)).type, 'image/png');
  assert.equal((await a.getSimilarImage('case')).type, 'image/png');
  globalThis.fetch = async () => new Response(JSON.stringify(error415), { status: 415 });
  await assert.rejects(a.analyse(file), {
    message: error415.error.message,
    status: 415,
    code: 'unsupported_media_type',
  });
  await assert.rejects(a.getCaseImage('missing'), { message: error415.error.message });
});

test('all pending cases can be reviewed into an empty queue without touching retakes', async () => {
  const a = await api();
  globalThis.fetch = () => {
    throw new Error('Demo must not access the network');
  };
  for (const c of (await a.getCases()).cases) {
    await a.postDecision(c.case_id, { action: 'accept', reviewer: 'Dr. Test' });
  }
  assert.deepEqual(await a.getCases(), { cases: [], total: 0 });
  assert.equal((await a.getCases('retake')).cases[0].case_id, retake.case_id);
  assert.equal(await a.getCaseImage(graded.case_id), null);
  assert.equal(await a.getSimilarImage('missing'), null);
  assert.equal((await a.getOperatingCurve()).mock, true);
  assert.equal((await a.getHealth()).model.mock, true);
});

test('malformed reachable health response is an error, not a fixture fallback', async () => {
  const a = await api('');
  globalThis.fetch = async () => new Response('not JSON', { status: 200 });
  await assert.rejects(a.initialiseApi(), { message: 'The API returned invalid JSON.' });
  assert.equal(a.isDemoMode(), false);
});
