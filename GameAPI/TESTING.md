
## **Testing the API**

This document explains how to test the API endpoints using tools like **cURL** or **Postman**, covering admin and game provider operations across five categories.

### **1. Start the Flask Application**

Ensure the Flask application is running:

```bash
python run.py

```

The API will be available at: [http://localhost]:8080]

### **2. Set Up the Database**

Populate the Provider table with initial data before testing game provider endpoints.

#### **Run the Seed Script**

Ensure `seed_providers.py` is updated (see README.md for setup).

```bash
python seed_providers.py

```

This clears and repopulates the table with 17 providers across Categories 1–5.

#### **Verify Providers**

Open a Flask shell:

```bash
flask shell

```

Check data:

```python
from app.models import Provider
for p in Provider.query.all():
    print(p.to_dict())

```

Note `provider_id` values (e.g., 1 for Gameroom, 11 for Panda Master).

### **3. Test Admin Endpoints**

#### **Admin Login**

-   **Endpoint:** `POST /admin/api/login`
-   **Request:**

```bash
curl -X POST [localhost]/admin/api/login \
-H "Content-Type: application/json" \
-d '{"username": "admin", "password": "admin123"}'

```

-   **Response:**

```json
{
    "message": "Login successful"
}

```

#### **Create a New Account**

-   **Endpoint:** `POST /admin/api/accounts`
-   **Request:**

```bash
curl -X POST [localhost]/admin/api/accounts \
-H "Content-Type: application/json" \
-d '{"username": "store1", "email": "store1@example.com", "password": "store123"}'

```

-   **Response:**

```json
{
    "id": 2,
    "username": "store1",
    "email": "store1@example.com",
    "type": "PLAYER",
    "created_at": "2025-02-21T12:05:00"
}

```

#### **Fetch All Accounts**

-   **Endpoint:** `GET /admin/api/accounts`
-   **Request:**

```bash
curl -X GET [localhost]/admin/api/accounts

```

-   **Response:**

```json
[
    {
        "id": 1,
        "username": "admin",
        "email": "admin@example.com",
        "type": "ADMIN",
        "created_at": "2025-02-21T12:00:00"
    }
]

```

### **4. Test Game Provider Endpoints**

Each category supports `login`, `add_user`, `recharge`, `redeem`, `reset_password`, `balance`, and `agent_balance`. Use `provider_id` from the Provider table (e.g., 1 for Gameroom, 7 for Game Vault, 11 for Panda Master).

#### **Category 1 (e.g., Gameroom, provider_id: 1)**

##### **Login**

```bash
curl -X POST [localhost]/category1/login \
-H "Content-Type: application/json" \
-d '{"provider_id": 1, "username": "<agent-id>", "password": "<secret-key>"}'

```

##### **Add User**

```bash
curl -X POST [localhost]/category1/add_user \
-H "Content-Type: application/json" \
-d '{"provider_id": 1, "new_username": "player1", "new_password": "player123"}'

```

##### **Recharge**

```bash
curl -X POST [localhost]/category1/recharge \
-H "Content-Type: application/json" \
-d '{"provider_id": 1, "username": "player1", "amount": 50.0}'

```

##### **Redeem**

```bash
curl -X POST [localhost]/category1/redeem \
-H "Content-Type: application/json" \
-d '{"provider_id": 1, "username": "player1", "amount": 20.0}'

```

##### **Reset Password**

```bash
curl -X POST [localhost]/category1/reset_password \
-H "Content-Type: application/json" \
-d '{"provider_id": 1, "username": "player1", "new_password": "newpass123"}'

```

##### **Balance**

```bash
curl -X POST [localhost]/category1/balance \
-H "Content-Type: application/json" \
-d '{"provider_id": 1, "username": "player1"}'

```

##### **Agent Balance**

```bash
curl -X POST [localhost]/category1/agent_balance \
-H "Content-Type: application/json" \
-d '{"provider_id": 1}'

```

### **Using Swagger for API Documentation**

Swagger provides an interactive UI to explore and test all API endpoints.

#### **1. Access Swagger UI**

Navigate to:

```
http://localhost/swagger/

```

#### **2. Explore Endpoints**

-   **Admin API:**
    -   `/admin/api/login` (POST)
    -   `/admin/api/accounts` (GET, POST)
    -   `/admin/api/tokens` (GET, POST)
    -   `/admin/api/logs` (GET)
-   **Game Provider API (Categories 1–5):**
    -   `/categoryX/login`, `/add_user`, `/recharge`, `/redeem`, `/reset_password`, `/balance`, `/agent_balance` (POST) where `X` is `1–5`.

#### **3. Test Endpoints in Swagger**

1.  Click an endpoint (e.g., `POST /category1/add_user`).
2.  Click **Try it out**.
3.  Enter parameters (e.g., `provider_id: 1, new_username: "player1", new_password: "player123"`).
4.  Click **Execute**.
5.  View the response.

#### **Example: Testing `/category3/login`**

-   **Request:**

```json
{
    "provider_id": 11,
    "username": "password",
    "password": "password"
}

```

-   **Response:**

```json
{
    "message": "Login successful"
}

```

### **Additional Notes**

-   **Authentication:** Admin endpoints may require tokens from `/admin/api/login`. Game provider endpoints use provider-specific credentials.
-   **Provider IDs:** Use IDs from the Provider table (e.g., `1` for Gameroom). Verify with `flask shell` or `psql`.
-   **Error Handling:** Check logs (`app.log` or console) for detailed errors if a `400` or `500` response occurs.
-   **CAPTCHA:** Category 2 (e.g., Game Vault) requires a 2Captcha API key in `config.py` for login.

Let me know if you need further assistance! 🚀