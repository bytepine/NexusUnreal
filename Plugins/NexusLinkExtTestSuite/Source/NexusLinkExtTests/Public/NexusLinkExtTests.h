// Copyright byteyang. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

/**
 * NexusLinkExtTests —— NexusLinkExtTestSuite 的自动化测试宿主。
 * 只收集 IMPLEMENT_SIMPLE_AUTOMATION_TEST，过滤前缀 NexusLinkExt.
 */
class FNexusLinkExtTestsModule : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
};
