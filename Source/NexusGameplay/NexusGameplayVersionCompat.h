// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

// 跨版本编译兼容宏（对齐 NexusLink NexusVersionCompat.h）
// 业务代码用法：#if NG_UE_HAS_<语义>（禁止在本文件外写 NG_UE_AT_LEAST）

#ifndef ENGINE_MAJOR_VERSION
#include "Runtime/Launch/Resources/Version.h"
#endif

#define NG_UE_VERSION  (ENGINE_MAJOR_VERSION * 100 + ENGINE_MINOR_VERSION)

#define NG_UE_AT_LEAST(Major, Minor)  (NG_UE_VERSION >= (Major) * 100 + (Minor))

#define NG_UE_HAS_STATETREE_AI_COMPONENT  NG_UE_AT_LEAST(5, 5) // UStateTreeAIComponent 5.4 无 MODULE_API 导出
#define NG_UE_HAS_SKELMESH_BODY_SIMULATE_PHYSICS  NG_UE_AT_LEAST(5, 4) // USkeletalMeshComponent::SetBodySimulatePhysics
#define NG_UE_HAS_STATETREE_NODE_FORMATTING  NG_UE_AT_LEAST(5, 5) // GetDescription(..., EStateTreeNodeFormatting)
#define NG_UE_HAS_STATETREE_WEAK_EXEC_CONTEXT  NG_UE_AT_LEAST(5, 6) // MakeWeakExecutionContext / StateTreeAsyncExecutionContext
#define NG_UE_HAS_STATETREE_TRIVIAL_INSTANCEDATA_MACRO  NG_UE_AT_LEAST(5, 8) // STATETREE_POD_INSTANCEDATA → UE_STATETREE_*_INSTANCEDATA

#if NG_UE_HAS_STATETREE_TRIVIAL_INSTANCEDATA_MACRO
#define NG_STATETREE_POD_INSTANCEDATA  UE_STATETREE_CONSTRUCTED_TRIVIALLY_COPIED_NO_DESTRUCTOR_INSTANCEDATA
#else
#define NG_STATETREE_POD_INSTANCEDATA  STATETREE_POD_INSTANCEDATA
#endif
