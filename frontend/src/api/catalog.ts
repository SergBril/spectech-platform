import apiClient from './client';

export interface AttributeOption {
  id: number;
  value: string;
  numeric_value: number | null;
  sort_order: number;
  is_custom: boolean;
}

export interface AttributeDefinition {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  data_type: 'select' | 'number' | 'text' | 'boolean';
  unit: string | null;
  is_required: boolean;
  allow_custom_values: boolean;
  sort_order: number;
  options: AttributeOption[];
}

export interface Subcategory {
  id: number;
  code: string;
  name: string;
  icon: string | null;
  sort_order: number;
  attribute_count: number;
}

export interface CategoryTree {
  id: number;
  code: string;
  name: string;
  icon: string | null;
  description: string | null;
  sort_order: number;
  subcategories: Subcategory[];
}

export interface AttributeOptionCreate {
  value: string;
  numeric_value?: number | null;
}

export async function getCatalogTree(): Promise<CategoryTree[]> {
  const response = await apiClient.get('/catalog/tree');
  return response.data;
}

export async function getSubcategoryAttributes(
  subcategoryId: number
): Promise<AttributeDefinition[]> {
  const response = await apiClient.get(
    `/catalog/subcategories/${subcategoryId}/attributes`
  );
  return response.data;
}

export async function addCustomOption(
  attributeId: number,
  data: AttributeOptionCreate
): Promise<AttributeOption> {
  const response = await apiClient.post(
    `/catalog/attributes/${attributeId}/options`,
    data
  );
  return response.data;
}
