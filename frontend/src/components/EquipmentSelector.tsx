import React, { useEffect, useState } from 'react';
import {
  CategoryTree,
  Subcategory,
  AttributeDefinition,
  getCatalogTree,
  getSubcategoryAttributes,
  addCustomOption,
} from '../api/catalog';
import { Plus, ChevronDown, X } from 'lucide-react';

interface EquipmentSelectorProps {
  value?: {
    category_id?: number;
    subcategory_id?: number;
    attributes?: Record<string, any>;
  };
  onChange: (data: {
    category_id?: number;
    subcategory_id?: number;
    attributes: Record<string, any>;
  }) => void;
}

export const EquipmentSelector: React.FC<EquipmentSelectorProps> = ({
  value,
  onChange,
}) => {
  const [categories, setCategories] = useState<CategoryTree[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(
    value?.category_id || null
  );
  const [selectedSubcategoryId, setSelectedSubcategoryId] = useState<number | null>(
    value?.subcategory_id || null
  );
  const [attributes, setAttributes] = useState<AttributeDefinition[]>([]);
  const [attributeValues, setAttributeValues] = useState<Record<string, any>>(
    value?.attributes || {}
  );
  const [loading, setLoading] = useState(false);
  const [showCustomInput, setShowCustomInput] = useState<Record<number, boolean>>({});
  const [customValues, setCustomValues] = useState<Record<number, string>>({});

  // Загружаем дерево категорий
  useEffect(() => {
    const loadCategories = async () => {
      try {
        setLoading(true);
        const data = await getCatalogTree();
        setCategories(data);
      } catch (error) {
        console.error('Failed to load catalog:', error);
      } finally {
        setLoading(false);
      }
    };
    loadCategories();
  }, []);

  // Загружаем атрибуты при выборе подкатегории
  useEffect(() => {
    if (selectedSubcategoryId) {
      const loadAttributes = async () => {
        try {
          setLoading(true);
          const attrs = await getSubcategoryAttributes(selectedSubcategoryId);
          setAttributes(attrs);
        } catch (error) {
          console.error('Failed to load attributes:', error);
        } finally {
          setLoading(false);
        }
      };
      loadAttributes();
    } else {
      setAttributes([]);
    }
  }, [selectedSubcategoryId]);

  // Получаем подкатегории выбранной категории
  const selectedCategory = categories.find((c) => c.id === selectedCategoryId);
  const subcategories = selectedCategory?.subcategories || [];

  // Обработчик выбора категории
  const handleCategoryChange = (categoryId: number | null) => {
    setSelectedCategoryId(categoryId);
    setSelectedSubcategoryId(null);
    setAttributeValues({});
    onChange({
      category_id: categoryId || undefined,
      subcategory_id: undefined,
      attributes: {},
    });
  };

  // Обработчик выбора подкатегории
  const handleSubcategoryChange = (subcategoryId: number | null) => {
    setSelectedSubcategoryId(subcategoryId);
    setAttributeValues({});
    onChange({
      category_id: selectedCategoryId || undefined,
      subcategory_id: subcategoryId || undefined,
      attributes: {},
    });
  };

  // Обработчик изменения атрибута
  const handleAttributeChange = (slug: string, value: any) => {
    const newValues = { ...attributeValues, [slug]: value };
    setAttributeValues(newValues);
    onChange({
      category_id: selectedCategoryId || undefined,
      subcategory_id: selectedSubcategoryId || undefined,
      attributes: newValues,
    });
  };

  // Обработчик добавления пользовательского варианта
  const handleAddCustomOption = async (attribute: AttributeDefinition) => {
    const customValue = customValues[attribute.id];
    if (!customValue?.trim()) return;

    try {
      const newOption = await addCustomOption(attribute.id, {
        value: customValue.trim(),
      });

      // Добавляем новый вариант в список
      setAttributes((prev) =>
        prev.map((attr) =>
          attr.id === attribute.id
            ? { ...attr, options: [...attr.options, newOption] }
            : attr
        )
      );

      // Выбираем новый вариант
      handleAttributeChange(attribute.slug, newOption.value);

      // Сбрасываем состояние
      setCustomValues((prev) => ({ ...prev, [attribute.id]: '' }));
      setShowCustomInput((prev) => ({ ...prev, [attribute.id]: false }));
    } catch (error: any) {
      console.error('Failed to add custom option:', error);
      alert(error.response?.data?.detail || 'Ошибка добавления варианта');
    }
  };

  // Рендер поля атрибута
  const renderAttributeField = (attr: AttributeDefinition) => {
    const value = attributeValues[attr.slug];

    switch (attr.data_type) {
      case 'select':
        return (
          <div key={attr.id} className="space-y-1">
            <label className="block text-sm font-medium text-gray-700">
              {attr.name}
              {attr.is_required && <span className="text-red-500 ml-1">*</span>}
            </label>
            <div className="flex gap-2">
              <select
                value={value || ''}
                onChange={(e) => handleAttributeChange(attr.slug, e.target.value)}
                className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required={attr.is_required}
              >
                <option value="">— Выберите —</option>
                {attr.options.map((opt) => (
                  <option key={opt.id} value={opt.value}>
                    {opt.value}
                    {opt.is_custom && ' (пользовательский)'}
                  </option>
                ))}
              </select>
              {attr.allow_custom_values && (
                <button
                  type="button"
                  onClick={() =>
                    setShowCustomInput((prev) => ({
                      ...prev,
                      [attr.id]: !prev[attr.id],
                    }))
                  }
                  className="px-3 py-2 border border-gray-300 rounded-md hover:bg-gray-50 flex items-center gap-1 text-sm"
                  title="Добавить свой вариант"
                >
                  <Plus className="w-4 h-4" />
                </button>
              )}
            </div>
            {showCustomInput[attr.id] && (
              <div className="flex gap-2 mt-2">
                <input
                  type="text"
                  value={customValues[attr.id] || ''}
                  onChange={(e) =>
                    setCustomValues((prev) => ({
                      ...prev,
                      [attr.id]: e.target.value,
                    }))
                  }
                  placeholder="Введите свой вариант"
                  className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm"
                />
                <button
                  type="button"
                  onClick={() => handleAddCustomOption(attr)}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
                >
                  Добавить
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setShowCustomInput((prev) => ({ ...prev, [attr.id]: false }))
                  }
                  className="px-3 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        );

      case 'number':
        return (
          <div key={attr.id} className="space-y-1">
            <label className="block text-sm font-medium text-gray-700">
              {attr.name}
              {attr.unit && <span className="text-gray-500 ml-1">({attr.unit})</span>}
              {attr.is_required && <span className="text-red-500 ml-1">*</span>}
            </label>
            <input
              type="number"
              step="0.01"
              value={value ?? ''}
              onChange={(e) =>
                handleAttributeChange(
                  attr.slug,
                  e.target.value === '' ? null : parseFloat(e.target.value)
                )
              }
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required={attr.is_required}
            />
          </div>
        );

      case 'text':
        return (
          <div key={attr.id} className="space-y-1">
            <label className="block text-sm font-medium text-gray-700">
              {attr.name}
              {attr.is_required && <span className="text-red-500 ml-1">*</span>}
            </label>
            <input
              type="text"
              value={value || ''}
              onChange={(e) => handleAttributeChange(attr.slug, e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required={attr.is_required}
            />
          </div>
        );

      case 'boolean':
        return (
          <div key={attr.id} className="flex items-center gap-2">
            <input
              type="checkbox"
              id={`attr-${attr.id}`}
              checked={value || false}
              onChange={(e) => handleAttributeChange(attr.slug, e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor={`attr-${attr.id}`} className="text-sm text-gray-700">
              {attr.name}
              {attr.is_required && <span className="text-red-500 ml-1">*</span>}
            </label>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="space-y-4">
      {/* Выбор категории */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Категория техники
        </label>
        <div className="relative">
          <select
            value={selectedCategoryId || ''}
            onChange={(e) =>
              handleCategoryChange(e.target.value ? Number(e.target.value) : null)
            }
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none"
          >
            <option value="">— Выберите категорию —</option>
            {categories.map((cat) => (
              <option key={cat.id} value={cat.id}>
                {cat.icon} {cat.name}
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
        </div>
      </div>

      {/* Выбор подкатегории */}
      {selectedCategoryId && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Подкатегория
          </label>
          <div className="relative">
            <select
              value={selectedSubcategoryId || ''}
              onChange={(e) =>
                handleSubcategoryChange(
                  e.target.value ? Number(e.target.value) : null
                )
              }
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none"
            >
              <option value="">— Выберите подкатегорию —</option>
              {subcategories.map((sub) => (
                <option key={sub.id} value={sub.id}>
                  {sub.icon} {sub.name} ({sub.attribute_count} атрибутов)
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
          </div>
        </div>
      )}

      {/* Динамическая форма атрибутов */}
      {selectedSubcategoryId && attributes.length > 0 && (
        <div className="border-t pt-4 mt-4">
          <h4 className="text-sm font-semibold text-gray-900 mb-3">
            📋 Характеристики техники
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {attributes.map((attr) => renderAttributeField(attr))}
          </div>
        </div>
      )}

      {loading && (
        <div className="text-center py-4">
          <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
        </div>
      )}
    </div>
  );
};
