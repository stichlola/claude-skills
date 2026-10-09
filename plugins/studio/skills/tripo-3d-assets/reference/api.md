# Tripo API v3 - the calls used

Base: `https://openapi.tripo3d.ai/v3`, header `Authorization: Bearer $TRIPO_API_KEY`.
Every JSON answer is `{"code": 0, "data": {...}}`; `code != 0` is an error. HTTP 401 = bad key.

| Call | Body (main fields) | Returns |
|---|---|---|
| `GET /account/balance` | - | `data.balance` |
| `POST /files` (multipart, field `file`) | image png/jpeg | `data.file_token` |
| `POST /generation/text-to-image` | `prompt` (≤1800 chars) | `task_id` → `output.generated_image_url` |
| `POST /generation/text-to-model` | `prompt` (≤1024), `negative_prompt`, `model_version`, `texture`, `pbr`, `texture_quality: "detailed"`, `smart_low_poly: true`, `face_limit` | `task_id` → `output.model_url`, `rendered_image_url` |
| `POST /generation/image-to-model` | `input` (an image task id or a `file_token`), `model_version` **or** `model: "P1-20260311"` / `"P2-20260801"`, `texture`, `pbr`, `texture_quality`, `smart_low_poly`, `face_limit` | as above |
| `POST /models/texture` | `input` (a model task id), `model` (e.g. `v3.0-20250812`), `texture_prompt: {image: {file_token}}` or text, `texture_quality`, `pbr` | `output.pbr_model_url` or `model_url` |
| `GET /tasks/<id>` | - | `status` (`queued`, `running`, `success`, other = failed), `progress`, `credits_consumed`, `output` |

Notes

- `model_version` used for text/image→3D: `v3.1-20260211`. Check the docs for newer ones before a big
  batch, and try one piece first.
- Face limits: text→3D floor 500; P1 50-20000; P2 48-50000 (quad mesh).
- Output URLs are signed CDN links: download them without the key, right away (they expire).
- Poll every ~4 s; a model takes 1-5 minutes. Time out after ~30 min and resume later by task id.
- `credits_consumed` on the finished task is the truth; compare it with the estimate.
