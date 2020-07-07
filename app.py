#!/usr/bin/env python3

from aws_cdk import core

from sls_website.sls_website_stack import SlsWebsiteStack


app = core.App()
SlsWebsiteStack(app, "sls-website")

app.synth()
