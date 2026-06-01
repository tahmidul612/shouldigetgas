import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

export default async function handler(_request) {
  const dataPath = join(process.cwd(), 'frontend', 'data', 'data.json');

  if (!existsSync(dataPath)) {
    return new Response(JSON.stringify({
      error: 'Data not available',
      meta: { updatedAt: null },
      wti: { price: 71.2, dir: 'flat', change: 0 },
      regions: [],
    }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  try {
    const raw = readFileSync(dataPath, 'utf-8');
    JSON.parse(raw); // validate
    return new Response(raw, {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (_err) {
    return new Response(JSON.stringify({ error: 'Failed to read data' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
