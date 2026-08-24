import axios from 'axios';
import type { ComplianceReport, RuleReference } from '../types';

const API_BASE = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const fetchHealth = async () => {
  const response = await api.get('/health');
  return response.data;
};

export const fetchRules = async (): Promise<{ rules: RuleReference[]; reference: string }> => {
  const response = await api.get('/compliance/rules');
  return response.data;
};

export const scanProductImage = async (formData: FormData): Promise<ComplianceReport> => {
  const response = await api.post('/scan', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const runOcr = async (formData: FormData): Promise<any> => {
  const response = await api.post('/ocr', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const uploadProductImage = async (formData: FormData): Promise<ComplianceReport> => {
  const response = await api.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const fetchReports = async (status?: string, query?: string): Promise<{ reports: ComplianceReport[]; total: number }> => {
  const params: Record<string, string> = {};
  if (status) params.status = status;
  if (query) params.query = query;
  
  const response = await api.get('/reports', { params });
  return response.data;
};

export const fetchReportDetail = async (id: number): Promise<ComplianceReport> => {
  const response = await api.get(`/reports/${id}`);
  return response.data;
};

export const getPdfDownloadUrl = (reportId: number): string => {
  return `${API_BASE}/reports/${reportId}/pdf`;
};

export const updateScanResult = async (formData: FormData): Promise<ComplianceReport> => {
  const response = await api.post('/scan/update', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};
