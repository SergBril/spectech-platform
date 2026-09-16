UPDATE companies SET
    name = 'ООО "СпецТехника Про"',
    legal_name = 'Общество с ограниченной ответственностью "СпецТехника Про"',
    inn = '7700000000',
    kpp = '770001001',
    legal_address = '123456, г. Москва, ул. Примерная, д. 1',
    bank_details = '{"account": "40702810000000012345", "bank_name": "ПАО Сбербанк", "bik": "044525225", "correspondent_account": "30101810400000000225"}'::json,
    timezone = 'Europe/Moscow',
    currency = 'RUB',
    default_tax_system = 'osno',
    default_vat_rate = 20.00,
    default_is_vat_included = true
WHERE id = 1;
