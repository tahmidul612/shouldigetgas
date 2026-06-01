export default {
  async fetch(_request) {
    const { readFileSync, existsSync } = await import('fs');
    const { join } = await import('path');
    const dataPath = join(process.cwd(), 'data', 'data.json');

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
    } catch (err) {
      return new Response(JSON.stringify({ error: 'Failed to read data' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      });
    }
  },
};
