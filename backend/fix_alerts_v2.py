import re

p = 'app/api/routes/telematics.py'
with open(p, encoding='utf-8') as f:
    content = f.read()

# Ищем блок проверки алертов в receive_single_gps_point
# Маркер: строка с "Проверка правил алертов" или "process_point_with_rules"
# Заканчивается: "logger.warning" с "Alert"

# Паттерн для поиска блока
pattern = r'(    # === Проверка правил алертов.*?)(    return \{)'

# Новый асинхронный блок
new_block = '''    # === Проверка правил алертов (в фоне) ===
    try:
        import asyncio
        from app.services.alert_engine import process_point_with_rules

        async def _check_alerts_bg():
            try:
                alerts = await asyncio.to_thread(
                    process_point_with_rules, db, gps_point, current_user.company_id or 0
                )
                for alert in alerts:
                    logger.info("Alert created: %s", alert.title)
                    alert_data = {
                        "id": alert.id,
                        "alert_type": alert.alert_type,
                        "severity": alert.severity.value if hasattr(alert.severity, "value") else alert.severity,
                        "status": alert.status.value if hasattr(alert.status, "value") else alert.status,
                        "vehicle_id": alert.vehicle_id,
                        "title": alert.title,
                        "description": alert.description,
                        "occurred_at": alert.occurred_at.isoformat() if alert.occurred_at else None,
                    }
                    await manager.broadcast_alert_to_company(current_user.company_id or 0, alert_data)
            except Exception as e:
                logger.warning("Alert processing failed: %s", e)

        asyncio.create_task(_check_alerts_bg())
    except Exception as e:
        logger.warning("Alert check setup failed: %s", e)

    \\2'''

new_content, count = re.subn(pattern, new_block, content, flags=re.DOTALL)

if count > 0:
    with open(p, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f'OK: Replaced {count} block(s) with async version')
else:
    print('Pattern not found, trying alternative approach...')
    # Альтернатива: ищем по строкам
    lines = content.split('\n')
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if 'process_point_with_rules' in line and start_idx is None:
            # Ищем начало блока (комментарий или try)
            for j in range(max(0, i-5), i):
                if 'Проверка правил' in lines[j] or 'try:' in lines[j]:
                    start_idx = j
                    break
            if start_idx is None:
                start_idx = i
        if start_idx is not None and 'return {' in line:
            end_idx = i
            break
    
    if start_idx is not None and end_idx is not None:
        print(f'Found block at lines {start_idx+1}-{end_idx+1}')
        # Вставляем асинхронный блок
        async_block = '''    # === Проверка правил алертов (в фоне) ===
    try:
        import asyncio
        from app.services.alert_engine import process_point_with_rules

        async def _check_alerts_bg():
            try:
                alerts = await asyncio.to_thread(
                    process_point_with_rules, db, gps_point, current_user.company_id or 0
                )
                for alert in alerts:
                    logger.info("Alert created: %s", alert.title)
                    alert_data = {
                        "id": alert.id,
                        "alert_type": alert.alert_type,
                        "severity": alert.severity.value if hasattr(alert.severity, "value") else alert.severity,
                        "status": alert.status.value if hasattr(alert.status, "value") else alert.status,
                        "vehicle_id": alert.vehicle_id,
                        "title": alert.title,
                        "description": alert.description,
                        "occurred_at": alert.occurred_at.isoformat() if alert.occurred_at else None,
                    }
                    await manager.broadcast_alert_to_company(current_user.company_id or 0, alert_data)
            except Exception as e:
                logger.warning("Alert processing failed: %s", e)

        asyncio.create_task(_check_alerts_bg())
    except Exception as e:
        logger.warning("Alert check setup failed: %s", e)

'''
        new_lines = lines[:start_idx] + async_block.split('\n') + lines[end_idx:]
        with open(p, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        print('OK: Replaced with async version (alternative)')
    else:
        print(f'ERROR: Could not find block. start={start_idx}, end={end_idx}')