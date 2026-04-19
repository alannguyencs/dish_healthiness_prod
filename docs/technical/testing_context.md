# Testing Context

## Application Ports

| Application   | Port | URL                     | Purpose                                 |
|---------------|------|-------------------------|-----------------------------------------|
| Frontend      | 2512 | `http://localhost:2512` | React app — all feature UI lives here   |
| Backend API   | 2612 | `http://localhost:2612` | FastAPI server                          |

## Test User

| Username | Purpose            |
|----------|--------------------|
| Alan     | E2E workflow tests |

## Sign-in Procedure

No sign-in required. Navigate to `http://localhost:2512` and proceed directly with the testing workflow.

## Sign-out Procedure

Not applicable — this project does not require a sign-in flow for local testing.

## Access Tokens

Loaded from `.env`:
- `USER_ACCESS_TOKEN` — bearer token for authenticating API requests on behalf of test user `Alan`.

## Canonical Test Images

Three URL-upload canaries that map 1-to-1 onto the four nutrition source DBs (Malaysian, MyFCD, Anuvaad, CIQUAL). Each image is chosen to produce a high-confidence match in its target DB so regression tests can assert `nutrition_db_matches` is populated from the expected source.

| Dish | Target DB | Image URL |
|------|-----------|-----------|
| Ayam Goreng (Malaysian fried chicken) | Malaysian / MyFCD | `https://www.marionskitchen.com/wp-content/uploads/2021/08/20201216_Malaysian-Fried-Chicken-Ayam-Goreng-11-Web-1024x1024-1.jpeg` |
| Daal Tadka (Indian tempered lentils)  | Anuvaad           | `https://healthy-indian.com/wp-content/uploads/2018/07/20200628_114659.jpg` |
| Quiche Lorraine (French savory tart)  | CIQUAL            | `https://www.theflavorbender.com/wp-content/uploads/2019/06/Quiche-Lorraine-Featured.jpg` |

All three are public CDN images — internet egress is required.

