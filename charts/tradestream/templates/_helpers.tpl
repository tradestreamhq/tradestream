{{- define "tradestream.fullname" -}} 
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "tradestream.name" -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- $name -}}
{{- end -}}
