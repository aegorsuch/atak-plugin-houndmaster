package com.atakmap.android.houndmaster.plugin;

import com.atak.plugins.impl.AbstractPlugin;
import com.atakmap.android.houndmaster.HoundmasterMapComponent;

import gov.tak.api.plugin.IServiceController;

public class HoundmasterLifecycle extends AbstractPlugin {
    public HoundmasterLifecycle(IServiceController serviceController) {
        super(serviceController, new HoundmasterMapComponent());
    }
}
