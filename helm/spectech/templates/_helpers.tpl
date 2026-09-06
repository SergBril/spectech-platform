{{/*
Common labels
*/}}
{{- define "spectech.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels for backend
*/}}
{{- define "spectech.backend.selectorLabels" -}}
app: backend
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Selector labels for frontend
*/}}
{{- define "spectech.frontend.selectorLabels" -}}
app: frontend
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
