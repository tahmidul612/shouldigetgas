import { readFileSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

export default function handler(req, res) {
  const dataPath = join(__dirname, '..', 'frontend', 'data', 'data.json');

  res.setHeader('Content-Type', 'application/json');

  if (!existsSync(dataPath)) {
    return res.status(404).json({
      error: 'Data not available',
      meta: { updatedAt: null },
      wti: { price: 71.2, dir: 'flat', change: 0 },
      regions: [],
    });
  }

  try {
    const raw = readFileSync(dataPath, 'utf-8');
    JSON.parse(raw); // validate
    res.status(200).send(raw);
  } catch (_err) {
    res.status(500).json({ error: 'Failed to read data' });
  }
}
