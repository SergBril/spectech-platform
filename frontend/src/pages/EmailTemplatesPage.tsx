import React, { useEffect, useState } from 'react';
import { Navbar } from '../components/Navbar';
import {
  EmailTemplate,
  EmailLog,
  getEmailTemplates,
  createEmailTemplate,
  updateEmailTemplate,
  deleteEmailTemplate,
  bulkSendEmails,
  getEmailLogs,
  EmailTemplateCreate,
} from '../api/emailTemplates';
import toast from 'react-hot-toast';
import { Mail, Plus, Edit, Trash2, Send, History, Eye, X } from 'lucide-react';

const TEMPLATE_TYPES = [
  { value: 'invoice_created', label: '📄 Создан счёт' },
  { value: 'invoice_overdue', label: '⏰ Просроченный счёт' },
  { value: 'act_created', label: '✅ Создан акт' },
  { value: 'act_signed', label: '✍️ Акт подписан' },
  { value: 'maintenance_completed', label: '🔧 ТО завершено' },
  { value: 'welcome', label: '👋 Приветствие' },
  { value: 'custom', label: '✏️ Пользовательский' },
];

const STATUS_COLORS = {
  pending: 'bg-gray-100 text-gray-800',
  sent: 'bg-blue-100 text-blue-800',
  delivered: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  bounced: 'bg-yellow-100 text-yellow-800',
};

export const EmailTemplatesPage: React.FC = () => {
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [logs, setLogs] = useState<EmailLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'templates' | 'logs' | 'bulk'>('templates');

  // Модалки
  const [showEditModal, setShowEditModal] = useState(false);
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<EmailTemplate | null>(null);

  // Форма массовой отправки
  const [bulkTemplateId, setBulkTemplateId] = useState<number>(0);
  const [bulkEmails, setBulkEmails] = useState('');
  const [bulkContext, setBulkContext] = useState('{}');
  const [sending, setSending] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [templatesData, logsData] = await Promise.all([
        getEmailTemplates(),
        getEmailLogs({ limit: 50 }),
      ]);
      setTemplates(templatesData);
      setLogs(logsData);
    } catch (error) {
      toast.error('Не удалось загрузить данные');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (templateId: number) => {
    if (!window.confirm('Удалить этот шаблон?')) return;
    try {
      await deleteEmailTemplate(templateId);
      toast.success('Шаблон удалён');
      loadData();
    } catch (error) {
      toast.error('Ошибка удаления');
    }
  };

  const handleBulkSend = async () => {
    if (!bulkTemplateId) {
      toast.error('Выберите шаблон');
      return;
    }

    const emails = bulkEmails
      .split(/[\n,;]+/)
      .map((e) => e.trim())
      .filter((e) => e && e.includes('@'));

    if (emails.length === 0) {
      toast.error('Введите хотя бы один email');
      return;
    }

    let context: Record<string, any>;
    try {
      context = JSON.parse(bulkContext);
    } catch {
      toast.error('Контекст должен быть валидным JSON');
      return;
    }

    setSending(true);
    try {
      const result = await bulkSendEmails({
        template_id: bulkTemplateId,
        recipient_emails: emails,
        context,
      });
      toast.success(`✅ Отправлено: ${result.sent} / ${result.total}`);
      if (result.failed > 0) {
        toast.error(`❌ Ошибок: ${result.failed}`);
      }
      setShowBulkModal(false);
      setBulkEmails('');
      setBulkContext('{}');
      loadData();
    } catch (error: any) {
      toast.error(`Ошибка: ${error.message}`);
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="flex justify-center items-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6 flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">📧 Email-рассылки</h1>
            <p className="text-gray-600 mt-1">
              Управление шаблонами и массовая отправка писем
            </p>
          </div>
          <button
            onClick={() => setShowBulkModal(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 flex items-center gap-2"
          >
            <Send className="w-4 h-4" />
            Массовая отправка
          </button>
        </div>

        {/* Tabs */}
        <div className="mb-6 border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('templates')}
              className={`py-3 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'templates'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              📋 Шаблоны ({templates.length})
            </button>
            <button
              onClick={() => setActiveTab('logs')}
              className={`py-3 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'logs'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <History className="inline w-4 h-4 mr-1" />
              История ({logs.length})
            </button>
          </nav>
        </div>

        {/* Tab: Шаблоны */}
        {activeTab === 'templates' && (
          <div className="bg-white rounded-lg shadow-sm overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Название
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Тип
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Тема
                  </th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                    Статус
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Действия
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {templates.map((template) => (
                  <tr key={template.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <Mail className="w-5 h-5 text-gray-400 mr-3" />
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {template.name}
                          </div>
                          {template.description && (
                            <div className="text-xs text-gray-500">
                              {template.description}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-sm text-gray-900">
                        {TEMPLATE_TYPES.find((t) => t.value === template.template_type)
                          ?.label || template.template_type}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-900 max-w-md truncate">
                        {template.subject}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      {template.is_active ? (
                        <span className="px-2 py-1 text-xs font-medium bg-green-100 text-green-800 rounded-full">
                          ✅ Активен
                        </span>
                      ) : (
                        <span className="px-2 py-1 text-xs font-medium bg-gray-100 text-gray-800 rounded-full">
                          ⏸ Неактивен
                        </span>
                      )}
                      {template.is_default && (
                        <span className="ml-2 px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                          ⭐ По умолчанию
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button
                        onClick={() => {
                          setEditingTemplate(template);
                          setShowEditModal(true);
                        }}
                        className="text-blue-600 hover:text-blue-900 mr-3"
                        title="Редактировать"
                      >
                        <Edit className="w-4 h-4 inline" />
                      </button>
                      <button
                        onClick={() => handleDelete(template.id)}
                        className="text-red-600 hover:text-red-900"
                        title="Удалить"
                      >
                        <Trash2 className="w-4 h-4 inline" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab: История */}
        {activeTab === 'logs' && (
          <div className="bg-white rounded-lg shadow-sm overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Дата
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Получатель
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Тема
                  </th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                    Статус
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Ошибка
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(log.created_at).toLocaleString('ru-RU')}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {log.to_email}
                      </div>
                      {log.to_name && (
                        <div className="text-xs text-gray-500">{log.to_name}</div>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-900 max-w-md truncate">
                        {log.subject}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <span
                        className={`px-2 py-1 text-xs font-medium rounded-full ${
                          STATUS_COLORS[log.status]
                        }`}
                      >
                        {log.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-red-600">
                      {log.error_message || '—'}
                    </td>
                  </tr>
                ))}
                {logs.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                      История отправок пуста
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Модальное окно: Массовая отправка */}
      {showBulkModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-200 flex justify-between items-center">
              <h3 className="text-xl font-bold text-gray-900">
                📧 Массовая отправка email
              </h3>
              <button
                onClick={() => setShowBulkModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Шаблон
                </label>
                <select
                  value={bulkTemplateId}
                  onChange={(e) => setBulkTemplateId(Number(e.target.value))}
                  className="w-full border border-gray-300 rounded-md px-3 py-2"
                >
                  <option value={0}>-- Выберите шаблон --</option>
                  {templates
                    .filter((t) => t.is_active)
                    .map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email получателей (через запятую, точку с запятой или с новой строки)
                </label>
                <textarea
                  value={bulkEmails}
                  onChange={(e) => setBulkEmails(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 font-mono text-sm"
                  rows={4}
                  placeholder="client1@example.com&#10;client2@example.com&#10;client3@example.com"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Получателей: {bulkEmails.split(/[\n,;]+/).filter((e) => e.trim() && e.includes('@')).length}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Контекст (JSON) — переменные для шаблона
                </label>
                <textarea
                  value={bulkContext}
                  onChange={(e) => setBulkContext(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 font-mono text-sm"
                  rows={6}
                  placeholder='{"order_number": "ТО-2026-0001", "vehicle_name": "Экскаватор", "total_cost": "35 250"}'
                />
                <p className="text-xs text-gray-500 mt-1">
                  Используйте в шаблоне как: {'{{ order_number }}'}, {'{{ vehicle_name }}'}
                </p>
              </div>
            </div>

            <div className="p-6 border-t border-gray-200 flex justify-end gap-2">
              <button
                onClick={() => setShowBulkModal(false)}
                disabled={sending}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Отмена
              </button>
              <button
                onClick={handleBulkSend}
                disabled={sending}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              >
                {sending ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    Отправка...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    Отправить
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модалка редактирования шаблона */}
      {showEditModal && editingTemplate && (
        <EditTemplateModal
          template={editingTemplate}
          onClose={() => {
            setShowEditModal(false);
            setEditingTemplate(null);
          }}
          onSave={() => {
            setShowEditModal(false);
            setEditingTemplate(null);
            loadData();
          }}
        />
      )}
    </div>
  );
};

// Компонент модалки редактирования
const EditTemplateModal: React.FC<{
  template: EmailTemplate;
  onClose: () => void;
  onSave: () => void;
}> = ({ template, onClose, onSave }) => {
  const [name, setName] = useState(template.name);
  const [subject, setSubject] = useState(template.subject);
  const [htmlBody, setHtmlBody] = useState(template.html_body);
  const [description, setDescription] = useState(template.description || '');
  const [isActive, setIsActive] = useState(template.is_active);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateEmailTemplate(template.id, {
        name,
        subject,
        html_body: htmlBody,
        description,
        is_active: isActive,
      });
      toast.success('Шаблон обновлён');
      onSave();
    } catch (error) {
      toast.error('Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-gray-200 flex justify-between items-center">
          <h3 className="text-xl font-bold text-gray-900">✏️ Редактировать шаблон</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Название
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Описание
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Тема письма
            </label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              placeholder="Акт № {{ order_number }}"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              HTML-тело письма
            </label>
            <textarea
              value={htmlBody}
              onChange={(e) => setHtmlBody(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 font-mono text-sm"
              rows={12}
            />
            <p className="text-xs text-gray-500 mt-1">
              Используйте переменные: {'{{ order_number }}'}, {'{{ vehicle_name }}'}, {'{{ total_cost }}'}
            </p>
          </div>

          <div className="flex items-center">
            <input
              type="checkbox"
              id="isActive"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="mr-2"
            />
            <label htmlFor="isActive" className="text-sm text-gray-700">
              Шаблон активен
            </label>
          </div>
        </div>

        <div className="p-6 border-t border-gray-200 flex justify-end gap-2">
          <button
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
          >
            Отмена
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default EmailTemplatesPage;
