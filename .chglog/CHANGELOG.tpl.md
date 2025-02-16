{{- $url := .Info.RepositoryURL }}
{{ if .Versions -}}
<a name="unreleased"></a>
## [Unreleased]

{{ if .Unreleased.CommitGroups -}}
{{ range .Unreleased.CommitGroups -}}
### {{ .Title }}
{{ range .Commits -}}
- {{ if .Hash }}[`{{ .Hash.Short }}`]({{ $url }}/commit/{{ .Hash.Long }}) {{ end }}{{ if .Scope }}**{{ .Scope }}:** {{ end }}{{ .Subject }}
{{- if .Refs }} (
  {{- range $i, $v := .Refs -}}
    {{- if (ne $i 0)  }}, {{ end -}}
    #{{ $v.Ref }}
  {{- end }})
{{- end }}
{{ end }}
{{ end -}}
{{ end -}}
{{ end -}}

{{ range .Versions }}
<a name="{{ .Tag.Name }}"></a>
## {{ if .Tag.Previous }}[{{ .Tag.Name }}]{{ else }}{{ .Tag.Name }}{{ end }} - {{ datetime "2006-01-02" .Tag.Date }}
{{ range .CommitGroups -}}
### {{ .Title }}
{{ range .Commits -}}
- {{ if .Hash }}[`{{ .Hash.Short }}`]({{ $url }}/commit/{{ .Hash.Long }}) {{ end }}{{ if .Scope }}**{{ .Scope }}:** {{ end }}{{ .Subject }}
{{- if .Refs }} (
  {{- range $i, $v := .Refs -}}
    {{- if (ne $i 0)  }}, {{ end -}}
    #{{ $v.Ref }}
  {{- end }})
{{- end }}
{{ end }}
{{ end -}}

{{- if .RevertCommits -}}
### Reverts
{{ range .RevertCommits -}}
- {{ .Revert.Header }}
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
[Unreleased]: {{ .Info.RepositoryURL }}/compare/{{ $latest := index .Versions 0 }}{{ $latest.Tag.Name }}...HEAD
{{ range .Versions -}}
{{ if .Tag.Previous -}}
[{{ .Tag.Name }}]: {{ $.Info.RepositoryURL }}/compare/{{ .Tag.Previous.Name }}...{{ .Tag.Name }}
{{ end -}}
{{ end -}}
{{ end -}}