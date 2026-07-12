import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation, Trans } from "react-i18next";
import { Button, Koros } from "hds-react";
import BackLink from "../components/BackLink";
import FeedbackLink from "../components/FeedbackLink";
import { apiFetch } from "../services/api";
import useTheeeme from "../hooks/useTheeeme";

const PERSONA_LINKS = {
  Lala: [{ code: "La1aC1", key: "personaLalaLink2" }],
  Lele: [{ code: "L3L3C1", key: "personaLeleLink1" }],
  Lili: [{ code: "l1l1C1", key: "personaLiliLink1" }],
  Lolo: [{ code: "l0l0C1", key: "personaLoloLink1" }],
  Lulu: [{ code: "1u1uC1", key: "personaLuluLink1" }],
};

export default function WelcomePage() {
  const { t } = useTranslation();
  useEffect(() => {
    document.title = t("titles.welcome");
    localStorage.setItem("seenWelcome", "true");
  }, [t]);
  const [userName, setUserName] = useState("");
  const [accessibleCodes, setAccessibleCodes] = useState(() => new Set());

  useEffect(() => {
    apiFetch("/api/v1/auth/me/")
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => setUserName(data.name || data.email || ""))
      .catch(() => {});
  }, []);

  useEffect(() => {
    apiFetch("/api/v1/invited-collections/")
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) =>
        setAccessibleCodes(new Set((data || []).map((c) => c.code))),
      )
      .catch(() => {});
  }, []);
  const { tc, koro, btnStyle, btnSecondaryStyle } = useTheeeme();

  return (
    <div
      className="form-page"
      style={
        tc.color_02
          ? { backgroundColor: `var(--color-${tc.color_02})` }
          : undefined
      }
    >
      <div
        className="form-hero"
        style={
          tc.color_03
            ? {
                backgroundColor: `var(--color-${tc.color_03})`,
                "--hero-logo-color": `var(--color-${tc.color_02})`,
              }
            : undefined
        }
      >
        <div
          className="form-hero-content"
          style={
            tc.color_05
              ? { "--hero-text-color": `var(--color-${tc.color_05})` }
              : undefined
          }
        >
          <BackLink to="/" label={t("common.home")} />
          <div className="spacer-m" />
          {userName && (
            <p
              style={{
                fontSize: "var(--fontsize-heading-m)",
                fontWeight: 700,
                lineHeight: "var(--lineheight-m)",
                letterSpacing: "-0.2px",
                color: "var(--hero-text-color, var(--color-black-90))",
              }}
            >
              {t("welcome.greeting", { name: userName })}
            </p>
          )}
          <h1 className="form-hero-title">{t("welcome.pageTitle")}</h1>
          <div
            className="button-row-wide"
            style={{ paddingBottom: "var(--spacing-s)" }}
          >
            <Link
              to="/collections/new"
              state={{
                backPath: "/welcome",
                backLabel: t("welcome.pageTitle"),
              }}
            >
              <Button style={btnStyle}>{t("welcome.createCollection")}</Button>
            </Link>
            <Link
              to="/me/edit"
              state={{
                backPath: "/welcome",
                backLabel: t("welcome.pageTitle"),
              }}
            >
              <Button variant="secondary" style={btnSecondaryStyle}>
                {t("welcome.editProfile")}
              </Button>
            </Link>
          </div>
        </div>
        <Koros
          className="form-hero-koros"
          type={koro}
          style={
            tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined
          }
        />
      </div>
      <div className="page-container welcome-content">
        <p
          style={{
            fontSize: "var(--fontsize-body-xl)",
            fontWeight: 700,
            lineHeight: "32px",
          }}
        >
          {t("welcome.description")}
        </p>
        <div className="spacer-m" />
        <p>{t("welcome.createShare")}</p>
        <div className="spacer-xl" />
        <h2>{t("welcome.commitmentTitle")}</h2>
        <div className="spacer-s" />
        <p>{t("welcome.commitmentBody1")}</p>
        <div className="spacer-s" />
        <p>
          <Trans
            i18nKey="welcome.commitmentBody2"
            components={[
              <span key="0" />,
              // eslint-disable-next-line jsx-a11y/anchor-has-content -- the link text is injected by <Trans> from the i18n string at runtime
              <a
                key="1"
                href="https://github.com/oiueei/standalone/blob/main/DESIGN.md#9-user-data-is-never-a-product"
                target="_blank"
                rel="noopener noreferrer"
              />,
            ]}
          />
        </p>
        <div className="spacer-xl" />
        <h2>{t("welcome.whoUsesTitle")}</h2>
        <div className="spacer-s" />
        <p>
          {accessibleCodes.size === 0
            ? t("welcome.exampleIntroEmpty")
            : t("welcome.exampleIntro")}
        </p>
        <div className="spacer-s" />
        {["Lala", "Lele", "Lili", "Lolo", "Lulu"].map((name, i) => (
          <div key={name}>
            {i > 0 && <div className="spacer-l" />}
            <p>
              <b>{t(`welcome.persona${name}Title`)}</b>{" "}
              {t(`welcome.persona${name}Body`)}
            </p>
            {(() => {
              const links = PERSONA_LINKS[name].filter(({ code }) =>
                accessibleCodes.has(code),
              );
              if (links.length === 0) return null;
              return (
                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: "var(--spacing-xs)",
                    marginTop: "var(--spacing-xs)",
                  }}
                >
                  {links.map(({ code, key }) => (
                    <Link
                      key={code}
                      to={`/collections/${code}`}
                      style={{
                        color: tc.color_01
                          ? `var(--color-${tc.color_01})`
                          : "var(--color-bus)",
                        textDecoration: "underline",
                        fontSize: "var(--fontsize-body-l)",
                        fontWeight: 700,
                      }}
                    >
                      {t(`welcome.${key}`)} →
                    </Link>
                  ))}
                </div>
              );
            })()}
          </div>
        ))}
        <div className="spacer-xl" />
        <div className="button-row-wide">
          <Link to="/">
            <Button style={btnStyle}>{t("welcome.enterCta")}</Button>
          </Link>
        </div>
        <FeedbackLink />
      </div>
    </div>
  );
}
