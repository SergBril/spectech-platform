UPDATE contractors SET
    legal_address = '123456, г. Москва, ул. Ленина, д. 10, оф. 5',
    bank_details = '{"account": "40702810400000012345", "bank_name": "ПАО Сбербанк", "bik": "044525225", "correspondent_account": "30101810400000000225"}'::jsonb,
    contact_name = 'Иванов Иван Иванович',
    contact_phone = '+7 (999) 888-77-66',
    contact_email = 'testclient@example.com',
    tax_system = 'osno'
WHERE id = 1;
