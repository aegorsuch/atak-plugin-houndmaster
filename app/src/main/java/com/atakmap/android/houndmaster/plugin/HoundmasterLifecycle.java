package com.atakmap.android.houndmaster.plugin;

import com.atak.plugins.impl.AbstractPlugin;
import com.atak.plugins.impl.PluginContextProvider;
import com.atakmap.android.houndmaster.HoundmasterMapComponent;

import gov.tak.api.plugin.IServiceController;

public class HoundmasterLifecycle extends AbstractPlugin {
    public HoundmasterLifecycle(IServiceController serviceController) {
        super(serviceController,
                new HoundmasterTool(serviceController.getService(PluginContextProvider.class).getPluginContext()),
                new HoundmasterMapComponent());
    }
}
