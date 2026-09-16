UPDATE contractors SET
    legal_address = '109012, г. Москва, ул. Варварка, д. 7',
    bank_details = '{"account": "40702810500000054321", "bank_name": "АО Альфа-Банк", "bik": "044525593", "correspondent_account": "30101810200000000593"}'::jsonb,
    contact_name = 'Петрова Мария Ивановна',
    contact_phone = '+7 (495) 123-45-67',
    contact_email = 'romashka@example.com'
WHERE id = 2;
