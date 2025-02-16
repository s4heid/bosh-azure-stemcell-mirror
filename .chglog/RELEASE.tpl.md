{{- $url := .Info.RepositoryURL }}
{{ range .Versions }}
## Changes {{ if .Tag.Previous }}since [{{ .Tag.Previous.Name }}]{{ else }}by Kind{{ end }}
{{ range .CommitGroups -}}
### {{ .Title }}
{{ range .Commits -}}
- {{ if .Hash }}[`{{ .Hash.Short }}`]({{ $url }}/commit/{{ .Hash.Long }}) {{ end }}{{ if .Scope }}**{{ .Scope }}:** {{ end }}{{ .Subject }}
{{- if .Refs }} (
  {{- range $i, $v := .Refs -}}
    {{- if (ne $i 0)  }}, {{ end -}}
    {{ $v.Ref }}
  {{- end }})
{{- end }}
{{ end }}
{{ end -}}

{{- if .NoteGroups -}}
{{ range .NoteGroups -}}
### {{ .Title }}
{{ range .Notes }}
{{ .Body }}
{{ end }}
{{ end -}}
{{ end -}}
{{ end -}}

{{- if .Versions }}
{{ range .Versions -}}
{{ if .Tag.Previous -}}
[{{ .Tag.Previous.Name }}]: {{ $.Info.RepositoryURL }}/compare/{{ .Tag.Previous.Name }}...{{ .Tag.Name }}
{{ end -}}
{{ end -}}
{{ end -}}