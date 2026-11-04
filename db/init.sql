-- Loan Assistant (Module 2) — synthetic demo schema
-- All data is fictional (proposal §5.5: no real customer data in demo)

CREATE TABLE applicants (
    applicant_id   TEXT PRIMARY KEY,        -- 'AP-1001'
    full_name      TEXT NOT NULL,
    pan_number     TEXT,                    -- NULL = missing-field edge case
    employer       TEXT,
    monthly_income NUMERIC(12,2),           -- NULL = refusal path
    kyc_verified   BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE loans (
    loan_id        TEXT PRIMARY KEY,        -- 'LN-1025'
    applicant_id   TEXT NOT NULL REFERENCES applicants(applicant_id),
    loan_amount    NUMERIC(12,2) NOT NULL,
    emi_amount     NUMERIC(12,2) NOT NULL,
    tenure_months  INT NOT NULL,
    status         TEXT NOT NULL,           -- 'active' / 'closed'
    disbursed_date DATE NOT NULL
);

CREATE TABLE repayments (
    id         SERIAL PRIMARY KEY,
    loan_id    TEXT NOT NULL REFERENCES loans(loan_id),
    record_id  TEXT NOT NULL UNIQUE,        -- 'PAY-201'
    due_date   DATE NOT NULL,
    paid_date  DATE,                        -- NULL when missed
    amount     NUMERIC(12,2) NOT NULL,
    status     TEXT NOT NULL                -- 'paid' / 'missed' / 'upcoming'
);

CREATE TABLE role_field_permissions (
    role       TEXT NOT NULL,               -- 'credit_manager' / 'support_agent'
    table_name TEXT NOT NULL,
    field_name TEXT NOT NULL,
    allowed    BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (role, table_name, field_name)
);

CREATE TABLE audit_logs (
    audit_id       TEXT PRIMARY KEY,        -- 'AUD-10001'
    user_id        TEXT NOT NULL,
    role           TEXT NOT NULL,
    question       TEXT NOT NULL,
    intent         TEXT,
    tools_called   TEXT[],
    source_records TEXT[],
    verified_result TEXT,
    outcome        TEXT NOT NULL,           -- 'answered' / 'refused' / 'denied'
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_repayments_loan ON repayments(loan_id);