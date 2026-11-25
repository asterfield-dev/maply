// SPDX-License-Identifier: Apache-2.0
package account

import (
	"bytes"
	"html/template"
	"net/http"
	"net/url"
	"strings"

	"github.com/asterfield-dev/maply/internal/i18n"
)

// The privacy page, in every language maply speaks: what is kept, what other
// players see, and how to delete the account. Google asks for it on the
// sign-in screen. It has no script and asks the database for nothing.

const privacyCSP = "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"

// The owner's Telegram, for erasing answers: "{contact}" in a line becomes
// this link. The rest of the line stays text.
const privacyContact = `<a href="https://t.me/amtiyo" dir="ltr">@amtiyo</a>`

var privacyPage = template.Must(template.New("privacy").Parse(`<!doctype html>
<html lang="{{.Lang}}" dir="{{.Dir}}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#245A3C">
<title>{{.Title}} · maply</title>
<link rel="icon" href="/icon/maply.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/icon/maply-180.png">
<style>
:root { --field: #245A3C; --deep: #1A412B; --ink: #FFFFFF; --soft: #D8E1DC; --muted: #B5C7BD; }
* { box-sizing: border-box; }
html, body { margin: 0; background: var(--field); color: var(--ink); }
body { font: 400 17px/1.5 "Sofia Sans", system-ui, sans-serif; -webkit-font-smoothing: antialiased; }
main { max-width: 680px; margin: 0 auto; padding: 24px 16px 48px; }
header { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; margin-bottom: 24px; }
.mark { font: 700 32px/1 "DIN Condensed", "Sofia Sans Extra Condensed", sans-serif; color: var(--ink); text-decoration: none; }
h1 { font: 700 40px/1.05 "DIN Condensed", "Sofia Sans Extra Condensed", sans-serif; margin: 0 0 12px; }
h2 { font: 700 24px/1.1 "DIN Condensed", "Sofia Sans Extra Condensed", sans-serif; color: var(--ink); margin: 32px 0 8px; }
p, li { color: var(--soft); }
ul { margin: 0; padding-inline-start: 20px; }
li + li { margin-top: 6px; }
a { color: var(--ink); }
nav { margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--deep); display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 15px; }
nav a { color: var(--muted); text-decoration: none; }
nav a[aria-current] { color: var(--ink); }
</style>
</head>
<body>
<main>
<header><a class="mark" href="/">maply</a><a href="{{.BackHref}}">{{.Back}}</a></header>
<h1>{{.Title}}</h1>
<p>{{.Intro}}</p>
{{range .Sections}}<h2>{{.Head}}</h2>
<ul>{{range .Items}}<li>{{.}}</li>{{end}}</ul>
{{end}}
<nav aria-label="{{.Languages}}">{{range .Langs}}<a href="{{$.Path}}?lang={{.Code}}" hreflang="{{.Code}}" lang="{{.Code}}"{{if .Current}} aria-current="page"{{end}}>{{.Name}}</a>{{end}}</nav>
</main>
</body>
</html>
`))

type privacySection struct {
	Head  string
	Items []template.HTML
}

type privacyLang struct {
	Code, Name string
	Current    bool
}

// siteHost is the site's address as the privacy page names it: the host of
// APP_URL, else the host the page was asked on. The domain may move, so no
// text carries it.
func (s *Service) siteHost(r *http.Request) string {
	if u, err := url.Parse(s.cfg.AppURL); err == nil && u.Host != "" {
		return u.Host
	}
	return r.Host
}

// Privacy serves /privacy in ?lang=, else the browser's first language maply
// speaks, else English.
func (s *Service) Privacy() http.Handler {
	return s.textPage("/privacy", "acct.privacy.title", "acct.privacy.intro", "acct.privacy.back", "/",
		"keep", "use", "google", "see", "not", "delete", "who")
}

// About serves /about the same way: what maply is and how to play, for
// whoever has no Telegram and no script, Google's brand review among them.
// It is the home page the sign-in screen names.
func (s *Service) About() http.Handler {
	return s.textPage("/about", "acct.about.title", "acct.about.intro", "acct.about.back", "/",
		"play", "account", "photos", "who")
}

// The links a line of a text page may carry: "{contact}" is the owner's
// Telegram, "{privacy}" the privacy page in the page's language.
func pageLine(lang, line string) template.HTML {
	out := strings.ReplaceAll(template.HTMLEscapeString(line), "{contact}", privacyContact)
	privacy := `<a href="/privacy?lang=` + lang + `">` + template.HTMLEscapeString(i18n.T(lang, "acct.privacy.title")) + `</a>`
	return template.HTML(strings.ReplaceAll(out, "{privacy}", privacy))
}

// textPage serves one of the static pages: a title, an intro and sections
// whose keys are prefix+"."+name+"_h" for the head and prefix+"."+name for
// the lines, one item per line.
func (s *Service) textPage(path, titleKey, introKey, backKey, backHref string, sections ...string) http.Handler {
	prefix := strings.TrimSuffix(titleKey, ".title")
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		lang := privacyLangOf(r)
		site := s.siteHost(r)
		var secs []privacySection
		for _, name := range sections {
			var items []template.HTML
			for _, line := range strings.Split(i18n.T(lang, prefix+"."+name, "site", site), "\n") {
				items = append(items, pageLine(lang, line))
			}
			secs = append(secs, privacySection{i18n.T(lang, prefix+"."+name+"_h"), items})
		}
		data := map[string]any{
			"Lang": lang, "Dir": "ltr", "Path": path, "BackHref": backHref,
			"Title": i18n.T(lang, titleKey), "Intro": i18n.T(lang, introKey, "site", site),
			"Back": i18n.T(lang, backKey), "Languages": i18n.T(lang, "acct.privacy.languages"),
			"Sections": secs,
		}
		if lang == "ar" {
			data["Dir"] = "rtl"
		}
		var langs []privacyLang
		for _, code := range i18n.Codes() {
			name := i18n.LabelOf(code)
			// The label leads with a flag; the page lists the names.
			if _, rest, ok := strings.Cut(name, " "); ok {
				name = rest
			}
			langs = append(langs, privacyLang{Code: code, Name: name, Current: code == lang})
		}
		data["Langs"] = langs
		var buf bytes.Buffer
		if err := privacyPage.Execute(&buf, data); err != nil {
			s.log.Error("text page", "path", path, "error", errClass(err))
			http.Error(w, "internal error", http.StatusInternalServerError)
			return
		}
		h := w.Header()
		h.Set("Content-Type", "text/html; charset=utf-8")
		h.Set("Content-Security-Policy", privacyCSP)
		h.Set("X-Content-Type-Options", "nosniff")
		h.Set("Referrer-Policy", "no-referrer")
		h.Set("Cache-Control", "public, max-age=3600")
		h.Set("Vary", "Accept-Language")
		_, _ = w.Write(buf.Bytes())
	})
}

func privacyLangOf(r *http.Request) string {
	if l := i18n.Normalize(r.URL.Query().Get("lang")); i18n.IsSupported(l) {
		return l
	}
	for _, part := range strings.Split(r.Header.Get("Accept-Language"), ",") {
		tag, _, _ := strings.Cut(part, ";")
		if l := i18n.Normalize(tag); i18n.IsSupported(l) {
			return l
		}
	}
	return i18n.DefaultLang
}
