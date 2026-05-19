import React from "react";
import { Link } from "react-router-dom";
import { AkvoIcon } from "../../../components/Icons";
import { config } from "../../../lib";

const HomeFooter = ({ text }) => {
  const phoneHref = `tel:${text.homeFooterContactPhone.replace(
    /\(|\)|\s/g,
    ""
  )}`;
  const emailHref = `mailto:${text.homeFooterContactEmail}`;

  return (
    <footer className="home-footer">
      <div className="footer-inner">
        <div className="footer-col">
          <Link to="/" className="footer-logo">
            <img src={config.siteLogo} alt="Footer Logo" />
          </Link>
        </div>
        <div className="footer-col">
          <h4>{text.homeFooterQuickLinksTitle}</h4>
          <ul>
            {text.homeQuickLinks.map((link, index) => (
              <li key={index}>
                {link.isPage ? (
                  <Link to={link.href}>{link.text}</Link>
                ) : (
                  <a href={link.href} target="_blank" rel="noopener noreferrer">
                    {link.text}
                  </a>
                )}
              </li>
            ))}
          </ul>
        </div>
        <div className="footer-col">
          <h4>{text.homeFooterContactTitle}</h4>
          <p className="addr">
            {text.homeFooterContactDetails.map((line, index) => (
              <React.Fragment key={index}>
                {line}
                <br />
              </React.Fragment>
            ))}
          </p>
          <p className="addr">
            {text.homeFooterContactAddress.map((line, index) => (
              <React.Fragment key={index}>
                {line}
                <br />
              </React.Fragment>
            ))}
          </p>
          <p className="addr">
            <span>{text.homeFooterPhoneLabel}</span>{" "}
            <a href={phoneHref}>{text.homeFooterContactPhone}</a>
          </p>
          <p className="addr">
            <span>{text.homeFooterEmailLabel}</span>{" "}
            <a href={emailHref}>{text.homeFooterContactEmail}</a>
          </p>
        </div>
        <div className="footer-col">
          <h4>{text.homeFooterAboutTitle}</h4>
          <p className="addr">{text.homeFooterAboutText}</p>
        </div>
      </div>
      <div className="footer-copyright">
        <p>{text.homeFooterCopyrightText}</p>
        <div className="powered-by">
          <span>{text.homeFooterPoweredByText}</span>
          <AkvoIcon />
        </div>
      </div>
    </footer>
  );
};

export default HomeFooter;
