INSERT INTO companies (
    name, legal_name, inn, kpp, legal_address, bank_details,
    timezone, currency, is_active,
    default_tax_system, default_vat_rate, default_is_vat_included,
    created_at, updated_at
) VALUES (
    'ИП Иванов А.С.',
    'Индивидуальный предприниматель Иванов Алексей Сергеевич',
    '772345678901',
    NULL,
    '105066, г. Москва, ул. Бауманская, д. 25',
    '{"account": "40802810200000098765", "bank_name": "АО Райффайзенбанк", "bik": "044525860", "correspondent_account": "30101810200000000860"}'::json,
    'Europe/Moscow',
    'RUB',
    true,
    'usn_6',
    0.00,
    true,
    NOW(),
    NOW()
);
